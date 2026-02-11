"""
Monthly Fee Deduction Service
Handles automatic monthly fee deduction from user accounts
"""

import stripe
import os
from datetime import datetime, timedelta
from typing import Tuple
import logging

from models.user import User
from models.payment import Payment
from models.paymentMethod import PaymentMethod
from models.defaultSettings import DefaultSettings
from helpers.email import send_email

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_API_KEY")


async def get_monthly_fee() -> int:
    """
    Retrieve monthly fee from default settings
    Returns:
        Monthly fee amount in cents
    """
    try:
        settings = await DefaultSettings.all().first()
        if settings and settings.monthly_fee:
            return settings.monthly_fee
        return 100  # Default to 100 if not found
    except Exception as e:
        logger.error(f"Error retrieving monthly fee: {str(e)}")
        return 100


async def get_payment_methods_for_user(user: User) -> list:
    """
    Get all payment methods for a user, primary first
    
    Args:
        user: User object
        
    Returns:
        List of PaymentMethod objects ordered by primary first
    """
    try:
        primary_method = await PaymentMethod.filter(
            user=user, 
            is_primary=True
        ).order_by("-created_at").first()
        
        other_methods = await PaymentMethod.filter(
            user=user, 
            is_primary=False
        ).order_by("-created_at")
        
        methods = []
        if primary_method:
            methods.append(primary_method)
        methods.extend(other_methods)
        
        return methods
    except Exception as e:
        logger.error(f"Error getting payment methods for user {user.id}: {str(e)}")
        return []


async def process_payment(
    user: User,
    amount: int,
    payment_method: PaymentMethod
) -> Tuple[bool, str]:
    """
    Process payment for a specific payment method
    
    Args:
        user: User object
        amount: Amount in cents
        payment_method: PaymentMethod object
        
    Returns:
        Tuple of (success: bool, payment_intent_id: str or error message)
    """
    try:
        # Get or create Stripe customer
        customers = stripe.Customer.list(email=user.email)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
            )
        
        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            customer=customer["id"],
            payment_method=payment_method.payment_method_id,
            off_session=True,
            confirm=True,
            automatic_payment_methods={
                'enabled': True,
                'allow_redirects': 'never',
            },
        )
        
        if payment_intent["status"] == "succeeded":
            # Log payment
            await Payment.create(
                user=user,
                amount_paid=payment_intent["amount"] / 100,
                amount_received=payment_intent["amount_received"] / 100,
                token=payment_intent["id"],
 
            )
            return True, payment_intent["id"]
        else:
            return False, f"Payment status: {payment_intent['status']}"
            
    except stripe.error.CardError as e:
        error_msg = f"Card error: {e.user_message if hasattr(e, 'user_message') else str(e)}"
        logger.warning(f"Card error for user {user.id}: {error_msg}")
        return False, error_msg
    except stripe.error.RateLimitError:
        error_msg = "Too many requests to Stripe API"
        logger.warning(f"Rate limit error for user {user.id}")
        return False, error_msg
    except stripe.error.InvalidRequestError as e:
        error_msg = f"Invalid request: {str(e)}"
        logger.warning(f"Invalid request for user {user.id}: {error_msg}")
        return False, error_msg
    except stripe.error.AuthenticationError:
        error_msg = "Stripe authentication failed"
        logger.error(f"Stripe auth error for user {user.id}")
        return False, error_msg
    except stripe.error.APIConnectionError:
        error_msg = "Network connection error with Stripe"
        logger.error(f"API connection error for user {user.id}")
        return False, error_msg
    except stripe.error.StripeError as e:
        error_msg = f"Stripe error: {e.user_message if hasattr(e, 'user_message') else str(e)}"
        logger.error(f"Stripe error for user {user.id}: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error processing payment for user {user.id}: {error_msg}")
        return False, error_msg


async def send_fee_reminder_email(user: User) -> bool:
    """
    Send email reminder to user about monthly fee
    
    Args:
        user: User object
        
    Returns:
        bool: Success status
    """
    try:
        subject = "Monthly Fee Payment Required for Your Account"
        message_html = f"""
        <html>
            <body>
                <p>Dear {user.name},</p>
                <p>Your monthly subscription fee is due. Please add funds to your account to continue using our services.</p>
                <p>If you have already paid this fee, please ignore this message.</p>
                <p>Thank you for using our service.</p>
                <br>
                <p>Best regards,<br>Helios AI Team</p>
            </body>
        </html>
        """
        send_email(user.email, subject, message_html)
        logger.info(f"Fee reminder email sent to user {user.id} ({user.email})")
        return True
    except Exception as e:
        logger.error(f"Failed to send reminder email to user {user.id}: {str(e)}")
        return False


async def deduct_monthly_fee_from_user(user: User) -> Tuple[bool, str]:
    """
    Attempt to deduct monthly fee from user
    
    Args:
        user: User object
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Skip if user is not active
    if not user.is_active:
        logger.info(f"Skipping inactive user {user.id}")
        return False, "User is not active"
    
    # Check if this user needs a reactivation check
    # (if admin reactivated but reminders were already sent)
    if user.fee_reminder_tries >= 2 and user.is_active:
        logger.warning(f"User {user.id} was reactivated by admin but max retries already reached")
        user.is_active = False
        await user.save()
        return False, "Account auto-deactivated due to max reminder attempts reached"
    
    # Check if fee deduction is needed
    now = datetime.utcnow()
    if user.last_fee_deducted is not None:
        next_deduction_date = user.last_fee_deducted + timedelta(days=30)
        if now < next_deduction_date:
            logger.debug(f"Monthly fee not due yet for user {user.id}. Next deduction: {next_deduction_date}")
            return False, "Monthly fee not due yet"
    
    # Get monthly fee amount
    monthly_fee = await get_monthly_fee()
    amount_cents = int(monthly_fee * 100)  # Convert to cents
    
    logger.info(f"Attempting to deduct monthly fee (${monthly_fee}) from user {user.id}")
    
    # Get all payment methods
    payment_methods = await get_payment_methods_for_user(user)
    
    if not payment_methods:
        logger.warning(f"No payment methods found for user {user.id}")
        # Send reminder email
        await send_fee_reminder_email(user)
        
        # Update reminder count and email flag
        user.fee_reminder_tries += 1
        user.fee_reminder_email = True
        
        # Check if max retries reached
        if user.fee_reminder_tries >= 2:
            logger.warning(f"Max reminders reached for user {user.id}. Deactivating account.")
            user.is_active = False
        
        await user.save()
        return False, "No payment methods available. Fee reminder email sent."
    
    # Try to process payment with each method
    payment_success = False
    last_error = ""
    
    for idx, payment_method in enumerate(payment_methods):
        logger.info(f"Attempting payment with method {idx + 1}/{len(payment_methods)} for user {user.id}")
        success, result = await process_payment(user, amount_cents, payment_method)
        
        if success:
            payment_success = True
            logger.info(f"Payment successful for user {user.id} using payment method {payment_method.id}")
            
            # Reset user fee-related fields on successful payment
            user.last_fee_deducted = now
            user.fee_reminder_tries = 0
            user.fee_reminder_email = False
            
            await user.save()
            return True, f"Monthly fee deducted successfully. Payment ID: {result}"
        else:
            last_error = result
            logger.warning(f"Payment attempt {idx + 1} failed for user {user.id}: {result}")
            # Continue to next payment method
    
    # All payment methods failed
    logger.error(f"All payment methods failed for user {user.id}. Last error: {last_error}")
    
    # Send reminder email
    await send_fee_reminder_email(user)
    
    # Update reminder count and email flag
    user.fee_reminder_tries += 1
    user.fee_reminder_email = True
    
    # Check if max retries reached
    if user.fee_reminder_tries >= 2:
        logger.warning(f"Max reminders reached for user {user.id}. Deactivating account.")
        user.is_active = False
    
    await user.save()
    return False, f"Payment failed with all methods. Fee reminder email sent. Error: {last_error}"


async def process_all_monthly_fees():
    """
    Process monthly fees for all active users
    This function should be called by a scheduled task (e.g., APScheduler, Celery)
    """
    logger.info("Starting monthly fee processing")
    
    try:
        # Get all users who are or should be checked
        users = await User.all()
        
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        
        for user in users:
            success, message = await deduct_monthly_fee_from_user(user)
            
            if success:
                successful_count += 1
            elif "not due yet" in message or "not active" in message:
                skipped_count += 1
            else:
                failed_count += 1
            
            logger.info(f"User {user.id} ({user.email}): {message}")
        
        summary = (
            f"Monthly fee processing completed. "
            f"Successful: {successful_count}, Failed: {failed_count}, Skipped: {skipped_count}"
        )
        logger.info(summary)
        return {
            "success": True,
            "message": summary,
            "successful": successful_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }
        
    except Exception as e:
        error_msg = f"Error processing monthly fees: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg,
        }
