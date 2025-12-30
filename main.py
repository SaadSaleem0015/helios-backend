
from dotenv import load_dotenv

from controllers.admin_controller import admin_router
from controllers.assistant_controller import assistant_router
from controllers.call_controller import calllogs_router
from controllers.defaultSettings_controller import default_settings_router
from controllers.documents_controller import kb_router
from controllers.schedule_call_controller import schedule_router
from controllers.terms_conditons_controller import terms_router
from controllers.twilio_controller import twilio_router

load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from helpers.tortoise_config import lifespan
from controllers.auth_controller import auth_router
from controllers.admin_statictics_controller import admin_statistics_router
from controllers.lead_controller import leads_router
from controllers.stripe_controller import stripe_router
from controllers.crm_controller import crm_router





app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)


app.include_router(auth_router, prefix='/api', tags=['Authentication'])
app.include_router(admin_statistics_router, prefix='/api', tags=['Admin Statistics'])
app.include_router(leads_router, prefix='/api', tags=['Leads Router'])
app.include_router(assistant_router, prefix='/api', tags=['Assistants'])
app.include_router(twilio_router, prefix='/api', tags=['Twilio Numbers'])
app.include_router(kb_router, prefix='/api', tags=['Knowledge base'])
app.include_router(calllogs_router, prefix = "/api" , tags = {"Call logs"})
app.include_router(stripe_router, prefix = "/api" , tags = {"Payments"})
app.include_router(schedule_router, prefix = "/api" , tags = {"Schedule Router"})
app.include_router(admin_router, prefix = "/api" , tags = {"Admin"})
app.include_router(terms_router, prefix = "/api" , tags = {"Terms "})
app.include_router(default_settings_router, prefix = "/api" , tags = {"Defualt Settings "})
app.include_router(crm_router, prefix='/api', tags=['CRM Integration'])











@app.get('/')
def greetings():
    return {
        "Message": "Hello Developers, how are you "
    }