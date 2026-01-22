import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import stripe
from helpers.jwt_token import get_current_user
from models.payment import Payment
from models.paymentMethod import PaymentMethod
from models.spent import Spent
from models.user import User
from models.auto_replenishment import AutoReplenishment
from typing import Annotated
import os
# from models.businessPlan import BusinessPlan
from models.super_admin_setting import SuperAdminSetting
from models.timeLimit import TimeLimit


stripe_router = APIRouter()


Domain = os.environ["DOMAIN"]
stripe.api_key = os.environ["STRIPE_API_KEY"]


class CheckoutRequest(BaseModel):
    price: int
class PaymentRequest(BaseModel):
    card_number: str
    expiry: str 
    cvc: str
    name_on_card: str
    address: str
    city: str
    state: str
    zip_code: str
    phone_number: str
    email: str
class makePayment(BaseModel):
    amount : int | float
    paymentMethodId: int


@stripe_router.get("/payments")
async def get_payments(user: Annotated[User, Depends(get_current_user)]):
    try:

        payments = await Payment.filter(user=user).order_by("id")

        return {
            "success" : True,
            "payments": payments
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching team data: {str(e)}")
        
@stripe_router.post("/payment-method")
async def save_payment_method(
    data: dict,
    user: User = Depends(get_current_user),

):
    try:
        payment_method_id = data["paymentMethodId"]

        customers = stripe.Customer.list(email=user.email)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
            )

        stripe.PaymentMethod.attach(payment_method_id, customer=customer["id"])

        has_primary = await PaymentMethod.filter(user=user, is_primary=True).exists()
        is_primary = not has_primary

        if is_primary:
            stripe.Customer.modify(
                customer["id"],
                invoice_settings={"default_payment_method": payment_method_id},
            )

        expiration_date = f"{data['exp_month']}/{data['exp_year']}"
        await PaymentMethod.create(
            user=user,
            name_on_card=data["name_on_card"],
            address=data["address"],
            city=data["city"],
            phone_number=data["phone_number"],
            state=data["state"],
            zip_code=data["zip_code"],
            last4=data["last4"],
            email=data["email"],
            expiration_date=expiration_date,
            is_primary=is_primary,
            stripe_customer_id=customer["id"],
            payment_method_id=payment_method_id,
        )
        # main_admin.free_trial_start = datetime.now(pytz.utc)
        # main_admin.has_free_trial = True
        
        await user.save()
        return {
            "success" : True, "detail" : "Payment Method Created Successfully"
        }
    except stripe.error.CardError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Card error: {e.user_message if hasattr(e, 'user_message') else str(e)}",
        )
    except stripe.error.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Too many requests made to the API too quickly.",
        )
    except stripe.error.InvalidRequestError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}",
        )
    except stripe.error.AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Authentication with Stripe's API failed. Check your API keys.",
        )
    except stripe.error.APIConnectionError:
        raise HTTPException(
            status_code=500,
            detail="Network communication with Stripe failed.",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe error: {e.user_message if hasattr(e, 'user_message') else str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}",
        )

@stripe_router.get("/user/payment-methods")
async def payment_method(
    user: Annotated[User, Depends(get_current_user)]
):
    try:
        methods = await PaymentMethod.filter(user=user) \
        .only('id', 'name_on_card', 'phone_number', 'email', 'is_primary', 'last4' , "expiration_date") \
        .order_by("-created_at")

        return methods

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@stripe_router.post("/primary-method/{id}")
async def set_primary_payment_method(
    id: int,
    user: Annotated[User, Depends(get_current_user)]
):
    try:
        primary_method = await PaymentMethod.get(id=id,user=user)
        if not primary_method:
            raise HTTPException(status_code=400, detail = "Payment method not found")
        if primary_method.is_primary:
            return {"success": True, "detail": "This payment method is already primary."} 
       
        await PaymentMethod.filter(user=user).update(is_primary = False)
        
        primary_method.is_primary = True
        await primary_method.save()     
        stripe.Customer.modify(
            primary_method.stripe_customer_id,
            invoice_settings={"default_payment_method": primary_method.payment_method_id},
        )  

        return {"success": True , "detail": "Payment method updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@stripe_router.delete("/remove-payment-method/{id}")
async def delete_payment_method(
    id: int,
    user: Annotated[User, Depends(get_current_user)]
):
    try:
        payment_method = await PaymentMethod.get(id=id, user=user)
        payment_methods = await PaymentMethod.filter(user=user).all().count()

        print("payment_methods",payment_methods)
        
        if payment_methods == 1:
           return  {"success": False, "detail": "You cannot delete your last payment method."}
        
        if not payment_method:
               raise HTTPException(status_code=404, detail="Payment method not found")

        if payment_method.is_primary:
            next_primary_method = await PaymentMethod.filter(user=user).exclude(id=id).order_by("-created_at").first()

            if next_primary_method:
                next_primary_method.is_primary = True
                await next_primary_method.save()

        await PaymentMethod.filter(id=id, user=user).delete()

        return {"success": True, "detail": "Payment method deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@stripe_router.get("/primary-method")
async def primaryMethod(user:Annotated[User, Depends(get_current_user)]):
    try:

        primaryMethod = await PaymentMethod.filter(user=user , is_primary=True).first()
        if not primaryMethod:
            return
        return primaryMethod
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@stripe_router.post("/make-payment")
async def makePayment(data: makePayment , user:Annotated[User, Depends(get_current_user)]):
    time_limit =  await TimeLimit.filter(user=user).first()
    try:
        primaryMethod = await PaymentMethod.filter(id=data.paymentMethodId).first()
        if not primaryMethod:
            return
        customers = stripe.Customer.list(email = user.email)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email =user.email,
                name = user.name
            )
        idempotency_key = str(uuid.uuid4())
        auto = False
        autoReplenishment = await AutoReplenishment.filter(user=user).first()
        if autoReplenishment:
           auto= autoReplenishment.replenishment

        payment_intent = stripe.PaymentIntent.create(
            amount = int(data.amount * 100) ,
            currency = "usd",
            customer=customer["id"],
            payment_method = primaryMethod.payment_method_id,
            off_session=auto,
            confirm = True,
            automatic_payment_methods={
           'enabled': True,
           'allow_redirects': 'never', 
    },
       idempotency_key=idempotency_key
        )
        if payment_intent["status"] == "succeeded":
            await Payment.create(
                user=user,
                amount_paid=payment_intent["amount"] / 100, 
                amount_received=payment_intent["amount_received"] / 100,
                auto_replenishment = auto,
                token=payment_intent["id"],  
            )
            # second_price = await SuperAdminSetting.filter(user=user).first()
            # for now chnage it later 
            second_price = 10
            # sec_assigned = second_price.seconds_per_dollar * payment_intent["amount"] / 100
            sec_assigned = second_price * payment_intent["amount"] / 100

            print("seconds assignes is this ",sec_assigned)
            print("time limit value ",time_limit)
            if not  time_limit :
                print("in if conditoin")
                await TimeLimit.create(
                    seconds= sec_assigned,
                    user = user
                )
            else:
                print("in else")
                sec_availabe = time_limit.seconds
                time_limit.seconds= sec_assigned+sec_availabe
                await time_limit.save()
            
            #set active subscription true
            user.has_active_subscription = True,
            await user.save()
            
            
            return {
                "success": True,
                "detail": "Payment successful.",
                "payment_intent_id": payment_intent["id"],
            }

        elif payment_intent["status"] == "requires_action":
            return {
                "success": False,
                "detail": "Payment requires additional authentication.",
                "payment_intent_id": payment_intent["id"],
            }

        else:
            return {
                "success": False,
                "detail": f"Payment failed with status: {payment_intent['status']}.",
            }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# @stripe_router.post("/subscribe-plan/{id}")
# async def subscribe_plan(id: int, user: Annotated[User, Depends(get_current_user)]):
#     main_admin = await User.filter(company_id=user.company_id, main_admin=True, role="company_admin").first()
#     if main_admin.subscribed_plan:
#        return {
#                 "success": False,
#                 "detail": "You have already a subsucribed plan.",
#     }
        
#     plan = await BusinessPlan.filter(id=id).first()
#     if not plan:
#         raise HTTPException(status_code=404, detail="Plan not found")

#     customers = stripe.Customer.list(email=main_admin.email)
#     primary_method = await PaymentMethod.filter(user=main_admin, is_primary=True).first()

#     if not primary_method or not primary_method.payment_method_id:
#         raise HTTPException(
#             status_code=400,
#             detail="No primary payment method found. Please add a payment method."
#         )

#     if customers.data:
#         customer = customers.data[0]
#     else:
#         customer = stripe.Customer.create(
#             email=main_admin.email,
#             name=main_admin.name
#         )

#     try:
#         payment_intent = stripe.PaymentIntent.create(
#             amount=int(plan.price * 100),
#             currency="usd",
#             customer=customer["id"],
#             payment_method=primary_method.payment_method_id,
#             confirm=True,
#             automatic_payment_methods={
#                 'enabled': True,
#                 'allow_redirects': 'never',
#             },
#         )

#         if payment_intent["status"] == "succeeded":
#             await Payment.create(
#                 user=main_admin,
#                 amount_paid=payment_intent["amount"] / 100,
#                 amount_received=payment_intent["amount_received"] / 100,
#                 token=payment_intent["id"],
#             )
#             await User.filter(id=main_admin.id).update(subscribed_plan = id)
#             s_user = await User.get(id=main_admin.id)
#             return {
#                 "success": True,
#                 "detail": "Payment successful.",
#                 "subscribed_plan" : s_user.subscribed_plan
#             }

#         elif payment_intent["status"] == "requires_action":
#             return {
#                 "success": False,
#                 "detail": "Payment requires additional authentication.",
#                 "payment_intent_id": payment_intent["id"],
#             }

#         else:
#             return {
#                 "success": False,
#                 "detail": f"Payment failed with status: {payment_intent['status']}.",
#             }

#     except stripe.error.StripeError as e:
#         raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
# @stripe_router.post("/cancel-subscription")
# async def cancel_subscription(user: Annotated[User, Depends(get_current_user)]):
#     try:
#         db_user = await User.filter(id=user.id).first()

#         if not db_user:
#             raise HTTPException(status_code=404, detail="User not found")

#         if db_user.has_free_trial and db_user.free_trial_start:
#             current_time = datetime.utcnow().replace(tzinfo=timezone.utc)

#             trial_end_date = db_user.free_trial_start + timedelta(days=14)

#             if current_time > trial_end_date:
#                 return {
#                     "success":False,
#                     "detail":"Trial period has ended, cannot cancel subscription."
#                 }
#             db_user.detect_after_trial = False
#             await db_user.save()

#             return {
#                 "success": True,
#                 "detail": "Subscription cancelled successfully within trial period."
#             }
#         else:
#             raise HTTPException(status_code=400, detail="User does not have an active trial.")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
# @stripe_router.get("/check-subscription")
# async def check_subscription_status(user: Annotated[User, Depends(get_current_user)]):
#     try:
#         db_user = await User.filter(id=user.id).first()

#         if not db_user:
#             raise HTTPException(status_code=404, detail="User not found")
        
#         subscription_status = db_user.detect_after_trial
        
        
#         show_cancel_subscription = True
        
#         if user.free_trial_start:
#             trial_start = user.free_trial_start.replace(tzinfo=timezone.utc)  
#             current_time = datetime.utcnow().replace(tzinfo=timezone.utc)  
            
#             trial_end_date = trial_start + timedelta(days=14)
            
#             print(current_time,trial_end_date)
            
#             if current_time >= trial_end_date:
#                 # print(f"in trials")
#                 show_cancel_subscription = False  
                
#         if user.free_trial_start is None:
#             show_cancel_subscription=False
        
#         return {
#             "success": True,
#             "subscriptionStatus": subscription_status,
#             "trialEndDate":None,
#             "detail": "Subscription status fetched successfully",
#             "showCancelSubscription":show_cancel_subscription
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")   
    

async def process_payment(payment_data: dict, user: User):
    try:
        primaryMethod = await PaymentMethod.filter(id=payment_data['paymentMethodId']).first()
        
        if not primaryMethod:
            raise HTTPException(status_code=404, detail="Payment method not found.")

        customers = stripe.Customer.list(email=user.email)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name
            )

        idempotency_key = str(uuid.uuid4())
        payment_intent = stripe.PaymentIntent.create(
            amount=int(payment_data['amount'] * 100),  # Amount in cents
            currency="usd",
            customer=customer["id"],
            payment_method=primaryMethod.payment_method_id,
            off_session=payment_data['autoReplenishment'],
            confirm=True,
            automatic_payment_methods={
                'enabled': True,
                'allow_redirects': 'never',
            },
            idempotency_key=idempotency_key
        )

        # Check if the payment was successful
        if payment_intent["status"] == "succeeded":
            await Payment.create(
                user=user,
                amount_paid=payment_intent["amount"] / 100,
                amount_received=payment_intent["amount_received"] / 100,
                auto_replenishment=payment_data['autoReplenishment'],
                token=payment_intent["id"],
            )

            second_price = await SuperAdminSetting.filter(user=user).first()
            sec_assigned = second_price.seconds_per_dollar * payment_intent["amount"] / 100

            time_limit = await TimeLimit.filter(user=user).first()
            if not time_limit:
                await TimeLimit.create(
                    seconds=sec_assigned,
                    user=user
                )
            else:
                time_limit.seconds += sec_assigned
                await time_limit.save()

            # Set active subscription true
            user.has_active_subscription = True
            await user.save()

            return {
                "success": True,
                "detail": "Payment successful.",
                "payment_intent_id": payment_intent["id"],
            }

        elif payment_intent["status"] == "requires_action":
            return {
                "success": False,
                "detail": "Payment requires additional authentication.",
                "payment_intent_id": payment_intent["id"],
            }

        else:
            return {
                "success": False,
                "detail": f"Payment failed with status: {payment_intent['status']}.",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@stripe_router.get("/spent-money")
async def spentmoney(user: Annotated[User, Depends(get_current_user)]):
    spent_money = await Spent.filter(user_id = user.id).all()
    return spent_money


@stripe_router.post("/toggle-replenishment")
async def toggle_replenishment(current_user: Annotated[User, Depends(get_current_user)]):
    replenishment_obj = await AutoReplenishment.get_or_none(user=current_user)
    
    if not replenishment_obj:
        replenishment_obj = await AutoReplenishment.create(user=current_user, replenishment=True)
        return {"message": "Replenishment enabled for the user.", "replenishment": True}
    
    # Toggle the boolean
    replenishment_obj.replenishment = not replenishment_obj.replenishment
    await replenishment_obj.save()
    
    status = "enabled" if replenishment_obj.replenishment else "disabled"
                
    return {"success": True, "detail": f"Replenishment {status}"}

@stripe_router.get("/replenishment-status")
async def replenishment_status(current_user: Annotated[User, Depends(get_current_user)]):
    replenishment_obj = await AutoReplenishment.get_or_none(user=current_user)
    
    if not replenishment_obj:
        return {"success": True, "replenishment": False, "detail": "Replenishment is disabled."}
    
    status = "enabled" if replenishment_obj.replenishment else "disabled"
    return {"success": True, "replenishment": replenishment_obj.replenishment, "detail": f"Replenishment is {status}."}
