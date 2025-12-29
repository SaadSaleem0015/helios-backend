from models.call_log import CallLog
from models.payment import Payment
from models.paymentMethod import PaymentMethod
from models.spent import Spent
from models.user import User
from tortoise.functions import Sum
from datetime import datetime, timedelta, timezone

async def has_payment_method(user) -> bool:
    payment_method = await PaymentMethod.filter(user=user).first()
    return payment_method is not None



# async def user_criteria_approved(user) -> bool:
#     active_user = await User.filter(id=user.id).first().values("criteria_approved", "has_free_trial", "free_trial_start")
    
#     if user.has_free_trial and user.free_trial_start:
#         trial_start = user.free_trial_start.replace(tzinfo=timezone.utc)  
#         current_time = datetime.utcnow().replace(tzinfo=timezone.utc)  

#         trial_end_date = trial_start + timedelta(days=14)
        
#         if current_time <= trial_end_date:
#             print("from free trial and can do action")
#             return True
#     if active_user:
#         return active_user["criteria_approved"]
    
#     return False




# async def user_criteria_approved(user) -> bool:
#     active_user = await User.filter(company=user.company_id, main_admin=True).first().values("criteria_approved")
    
#     print(f"user {active_user.has_free_trial}")
#     if active_user:
#         return active_user["criteria_approved"]
    
#     return False

async def check_balance(user_id: int) -> bool:
    user = await User.filter(id = user_id).first()
    total_amount_paid = await Payment.filter(user_id=user_id).annotate(
        total_paid=Sum("amount_paid")
    ).values("total_paid")

    total_cost = await Spent.filter(user_id=user_id).annotate(
        total_cost=Sum("spent_money")
    ).values("total_cost")

    total_amount_paid = total_amount_paid[0]["total_paid"] if total_amount_paid and total_amount_paid[0]["total_paid"] is not None else 0
    total_cost = total_cost[0]["total_cost"] if total_cost and total_cost[0]["total_cost"] is not None else 0

    total_amount_paid = float(total_amount_paid)
    total_cost = float(total_cost)
    
    balance = total_amount_paid - total_cost
    return balance > 0


async def balance_count(user_id: int) -> bool:
    user = await User.filter(id = user_id).first()
    total_amount_paid = await Payment.filter(user_id=user_id).annotate(
        total_paid=Sum("amount_paid")
    ).values("total_paid")

    total_cost = await Spent.filter(user_id=user_id).annotate(
        total_cost=Sum("spent_money")
    ).values("total_cost")

    total_amount_paid = total_amount_paid[0]["total_paid"] if total_amount_paid and total_amount_paid[0]["total_paid"] is not None else 0
    total_cost = total_cost[0]["total_cost"] if total_cost and total_cost[0]["total_cost"] is not None else 0

    total_amount_paid = float(total_amount_paid)
    total_cost = float(total_cost)
    
    balance = total_amount_paid - total_cost
    return balance 



async def can_process(user_id: int) -> bool:
    user = await User.filter(id=user_id).first()

    if not user:
        return False  

    
    if user.has_active_subscription:
        return False  

    if user.has_free_trial and user.free_trial_start:
        trial_start = user.free_trial_start.replace(tzinfo=timezone.utc)  
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)  
        
        trial_end_date = trial_start + timedelta(days=14)
        
        print(current_time,trial_end_date)
        
        if current_time <= trial_end_date:
            print(f"in trials")
            return True  
        
    return False  


async def can_buy_number(user_id: int) -> bool:
    user = await User.filter(id=user_id).first()

    if not user:
        return False  



    if user.has_active_subscription:
        return False  

    if user.has_free_trial:
        print("User has free trial - allowing purchase")
        return True
    
    if user.free_trial_start is None:
        print("Free trial not started yet - allowing purchase")
        return True
        
    return False 

async def can_process_call(user_id: int) -> bool:
    user = await User.filter(id=user_id).first()
    
    if not user:
        return False  



    if user.has_active_subscription:
        return True

    if user.has_free_trial:
            return True 

    return False  