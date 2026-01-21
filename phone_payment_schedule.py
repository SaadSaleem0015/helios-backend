import asyncio
from datetime import datetime, timedelta
from models.auto_replenishment import AutoReplenishment
from models.purchased_number import PurchasedNumber
from models.user import User
# from models.logs import Logs
from models.spent import Spent
from models.defaultSettings import DefaultSettings
from helpers.tortoise_config import init_tortoise
from helpers.criteria_check import balance_count
from models.paymentMethod import PaymentMethod
from models.payment import Payment
# from models.vv_adminSetting import VVadminSetting
from models.timeLimit import TimeLimit
import stripe
from pytz import UTC  
import os 
from dotenv import load_dotenv

import uuid

load_dotenv()


Domain = os.environ["DOMAIN"]
stripe.api_key = os.environ["STRIPE_API_KEY"]

async def check_and_deduct_payment():
    try:
        await init_tortoise()

        purchased_numbers = await PurchasedNumber.all().select_related("user")

        now = datetime.now(UTC)
        one_month_ago = now - timedelta(days=30)  

        found_users = []
        user_setting = await DefaultSettings.first()
        for purchased in purchased_numbers:
            user = purchased.user  
            balance = await balance_count(user.id)
            time_limit =  await TimeLimit.filter(user=user).first()
            phone_number = purchased.phone_number
            last_payment = purchased.last_month_payment
            created_at = purchased.created_at

            if balance < 5:
                continue
            auto_payment = await AutoReplenishment.filter(user=user).first()
            if auto_payment.replenishment:
                print("balance",balance)
                if balance < 200:
                    try:
                        primaryMethod = await PaymentMethod.filter(is_primary=True, user=user).first()
                        if not primaryMethod:
                            print("No primary payment method found.")
                            
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
                            amount=int(500 * 100),
                            currency="usd",
                            customer=customer["id"],
                            payment_method=primaryMethod.payment_method_id,
                            confirm=True,
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
                                auto_replenishment = True,
                                token=payment_intent["id"],
                            )
                            # second_price = await VVadminSetting.filter(user=user).first()

                            # sec_assigned = second_price.seconds_per_dollar * payment_intent["amount"] / 100
                            # print("Seconds assigned:", sec_assigned)
                            # print("Time limit value:", time_limit)
                            
                            # if not time_limit:
                            #     print("Creating new time limit entry.")
                            #     await TimeLimit.create(
                            #         seconds=sec_assigned,
                            #         user=user
                            #     )
                            # else:
                            #     print("Updating existing time limit.")
                            #     sec_available = time_limit.seconds
                            #     time_limit.seconds = sec_assigned + sec_available
                            #     await time_limit.save()

                            print({
                                "success": True,
                                "detail": "Payment successful.",
                                "payment_intent_id": payment_intent["id"],
                            })

                        elif payment_intent["status"] == "requires_action":
                            print({
                                "success": False,
                                "detail": "Payment requires additional authentication.",
                                "payment_intent_id": payment_intent["id"],
                            })

                        else:
                            print({
                                "success": False,
                                "detail": f"Payment failed with status: {payment_intent['status']}.",
                            })
                    except Exception as error:
                        print(f"error in this {error}")

                        
        

            if last_payment and last_payment < one_month_ago:
                found_users.append((user.name, user.email, phone_number))

                await Spent.create(
                user = user,
                spent_money = user_setting.phone_number_price,
                description = f"Monthly number fee deducted for {phone_number}."
                )

                # await Logs.create(
                #     user = user,
                #     message = f"Deducted monthly number fee for {phone_number}.",
                #     short_message = "number_monthly_fee"
                # )
                purchased.last_month_payment = now
                await purchased.save()


            elif last_payment is None and created_at and created_at < one_month_ago:
                found_users.append((user.name, user.email, phone_number))
                await Spent.create(
                user = user,
                spent_money = user_setting.phone_number_price,
                description = f"Monthly number fee deducted for {phone_number}."
                )

                # await Logs.create(
                #     user = user,
                #     message = f"Deducted monthly number cost for {phone_number}. ",
                #     short_message = "number_monthly_fee"
                # )
                purchased.last_month_payment = now
                await purchased.save()


        if found_users:
            print("Users who meet the criteria:")
            for user_name, user_email, phone in found_users:
                print(f"User: {user_name}, Email: {user_email}, Phone Number: {phone}")
        else:
            print("No users found for that criteria.")

    except Exception as error:
        print(f"Server error: {error}")

if __name__ == "__main__":
    asyncio.run(check_and_deduct_payment())
