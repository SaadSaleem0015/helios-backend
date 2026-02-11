from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from models.support_ticket import SupportTicket, TicketPriority, TicketStatus
from models.user import User
from helpers.jwt_token import get_current_user, get_admin   # ← admin wala function bana lo

support_router = APIRouter(prefix="/support", tags=["Support"])


# ========================== Schemas ==========================
class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketResponse(BaseModel):
    id: int
    ticket_number: str
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    admin_notes: Optional[str] = None


class MyTicketsResponse(BaseModel):
    tickets: List[TicketResponse]


class AdminTicketResponse(TicketResponse):
    user_id: int
    user_name: str
    user_email: str


class AdminTicketsResponse(BaseModel):
    tickets: List[AdminTicketResponse]


class StatusUpdate(BaseModel):
    status: TicketStatus
    admin_notes: Optional[str] = None


# ========================== USER APIs ==========================

@support_router.post("/tickets", response_model=TicketResponse)
async def create_ticket(data: TicketCreate, current_user: User = Depends(get_current_user)):
    # Ticket number generate (SUP-0001, SUP-0002 ...)
    last = await SupportTicket.all().order_by("-id").first()
    ticket_number = f"SUP-{str((last.id + 1) if last else 1).zfill(4)}"

    ticket = await SupportTicket.create(
        ticket_number=ticket_number,
        user=current_user,
        subject=data.subject,
        description=data.description,
        priority=data.priority,
    )

    return ticket


@support_router.get("/tickets", response_model=MyTicketsResponse)
async def get_my_tickets(current_user: User = Depends(get_current_user)):
    tickets = await SupportTicket.filter(user=current_user).order_by("-created_at")
    return {"tickets": tickets}


# ========================== ADMIN APIs ==========================

@support_router.get("/admin/tickets", response_model=AdminTicketsResponse)
async def admin_get_all_tickets(admin: User = Depends(get_admin)):
    tickets = await SupportTicket.all().prefetch_related("user").order_by("-created_at")

    result = []
    for t in tickets:
        result.append({
            **t.__dict__,
            "user_id": t.user.id,
            "user_name": t.user.name,
            "user_email": t.user.email,
        })

    return {"tickets": result}


@support_router.patch("/admin/tickets/{ticket_id}", response_model=AdminTicketResponse)
async def admin_update_ticket(
    ticket_id: int,
    data: StatusUpdate,
    admin: User = Depends(get_admin)
):
    ticket = await SupportTicket.get_or_none(id=ticket_id).prefetch_related("user")
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = data.status
    if data.admin_notes:
        ticket.admin_notes = data.admin_notes
    ticket.resolved_by = admin
    await ticket.save()

    return {
        **ticket.__dict__,
        "user_id": ticket.user.id,
        "user_name": ticket.user.name,
        "user_email": ticket.user.email,
    }