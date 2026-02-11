"""
Monthly Fee Deduction Service (Testing Version)
Uses print statements instead of logger
"""

import stripe
import os
from datetime import datetime,timezone
from typing import Tuple
from dateutil.relativedelta import relativedelta

from models.user import User
from models.payment import Payment
from models.paymentMethod import PaymentMethod
from models.defaultSettings import DefaultSettings
from helpers.email import send_email
import asyncio
stripe.api_key = os.environ.get("STRIPE_API_KEY")
from helpers.tortoise_config import init_tortoise
from tortoise import Tortoise

# ==============================
# GET MONTHLY FEE (IN DOLLARS)
# ==============================
async def get_monthly_fee() -> float:
    settings = await DefaultSettings.all().first()
    if settings and settings.monthly_fee:
        print(f"[INFO] Monthly fee fetched from settings: ${settings.monthly_fee}")
        return float(settings.monthly_fee)

    print("[WARNING] Monthly fee not found. Using default $100")
    return 100.0


# ==============================
# GET PAYMENT METHODS
# ==============================
async def get_payment_methods_for_user(user: User):
    print(f"[INFO] Fetching payment methods for user {user.id}")

    primary = await PaymentMethod.filter(user=user, is_primary=True).first()
    others = await PaymentMethod.filter(user=user, is_primary=False).order_by("-created_at")

    methods = []
    if primary:
        print("[INFO] Primary payment method found")
        methods.append(primary)

    methods.extend(others)

    print(f"[INFO] Total payment methods found: {len(methods)}")
    return methods


# ==============================
# PROCESS PAYMENT
# ==============================
async def process_payment(
    user: User,
    amount_cents: int,
    payment_method: PaymentMethod,
) -> Tuple[bool, str]:

    try:
        now = datetime.now(timezone.utc)
        idempotency_key = f"monthly_fee_{user.id}_{now.year}_{now.month}"

        print(f"[INFO] Attempting payment for user {user.id}")
        print(f"[INFO] Amount: {amount_cents/100}$")
        print(f"[INFO] Idempotency Key: {idempotency_key}")
        customers = stripe.Customer.list(email=user.email)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
            )
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer["id"],
            payment_method=payment_method.payment_method_id,
            off_session=True,
            confirm=True,
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never",
            },
            idempotency_key=idempotency_key,
        )

        print(f"[INFO] Stripe Status: {payment_intent['status']}")

        if payment_intent["status"] == "succeeded":

            await Payment.create(
                user=user,
                amount_paid=payment_intent["amount"] / 100,
                amount_received=payment_intent["amount_received"] / 100,
                token=payment_intent["id"],
            )

            print("[SUCCESS] Payment recorded in database")
            return True, payment_intent["id"]

        return False, payment_intent["status"]

    except Exception as e:
        print(f"[ERROR] Payment failed for user {user.id}: {str(e)}")
        return False, str(e)


# ==============================
# SEND REMINDER EMAIL
# ==============================
async def send_fee_reminder_email(user: User):
    print(f"[INFO] Sending reminder email to {user.email}")

    subject = "Monthly Fee Payment Required"
    message_html = f"""
    <p>Dear {user.name},</p>
    <p>Your monthly subscription fee could not be processed.</p>
    <p>Please update your payment method or ensure funds are available.</p>
    """

    send_email(user.email, subject, message_html)

    print("[INFO] Reminder email sent")


# ==============================
# CORE USER LOGIC
# ==============================
async def deduct_monthly_fee_from_user(user: User):

    print(f"\n==============================")
    print(f"[PROCESSING USER] {user.id} | {user.email}")
    print(f"==============================")

    if not user.is_active:
        print("[SKIPPED] User is inactive")
        return False, "User inactive"

    now = datetime.now(timezone.utc)

    # Check due date
    if user.last_fee_deducted:
        next_due = user.last_fee_deducted + relativedelta(months=1)
        print(f"[INFO] Next due date: {next_due}")

        if now < next_due:
            print("[SKIPPED] Monthly fee not due yet")
            return False, "Not due yet"

    monthly_fee_dollars = await get_monthly_fee()
    amount_cents = int(monthly_fee_dollars * 100)

    payment_methods = await get_payment_methods_for_user(user)

    payment_success = False
    last_error = ""

    for index, method in enumerate(payment_methods):
        print(f"[INFO] Trying payment method #{index+1}")

        success, result = await process_payment(user, amount_cents, method)

        if success:
            payment_success = True
            break
        else:
            print(f"[FAILED] Method #{index+1} failed: {result}")
            last_error = result

    # ========================
    # SUCCESS CASE
    # ========================
    if payment_success:
        user.last_fee_deducted = now
        user.fee_reminder_tries = 0
        user.fee_reminder_email = False
        await user.save()

        print("[SUCCESS] Monthly fee deducted successfully")
        return True, "Payment successful"

    # ========================
    # FAILURE CASE
    # ========================
    print("[INFO] All payment methods failed")

    if user.fee_reminder_tries >= 2:
        user.is_active = False
        await user.save()
        print("[DEACTIVATED] Account deactivated after admin reactivation check")
        return False, "Deactivated again"

    await send_fee_reminder_email(user)

    user.fee_reminder_tries += 1
    user.fee_reminder_email = True

    if user.fee_reminder_tries >= 2:
        user.is_active = False
        print("[DEACTIVATED] Account deactivated after 2 reminders")

    await user.save()

    print(f"[FAILED] Payment failed: {last_error}")
    return False, f"Payment failed: {last_error}"


# ==============================
# PROCESS ALL ACTIVE USERS
# ==============================
async def process_all_users_monthly_fee():

    print("\n========== STARTING MONTHLY FEE PROCESS ==========\n")

    users = await User.filter(is_active=True)

    successful = 0
    failed = 0
    skipped = 0

    for user in users:
        success, message = await deduct_monthly_fee_from_user(user)

        if success:
            successful += 1
        elif message == "Not due yet":
            skipped += 1
        else:
            failed += 1

        print(f"[RESULT] User {user.id}: {message}")

    print("\n========== PROCESS COMPLETE ==========")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")

    return {
        "success": True,
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
    }




async def main():
    print("Initializing database...")
    await init_tortoise()
    print("Database connected.")

    await process_all_users_monthly_fee()

    await Tortoise.close_connections()
    print("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
