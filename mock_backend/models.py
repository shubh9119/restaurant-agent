"""Pydantic models for the mock restaurant backend."""

from pydantic import BaseModel
from typing import Optional


class Table(BaseModel):
    id: int
    capacity: int
    location: str  # 'indoor' or 'outdoor'


class MenuItem(BaseModel):
    id: int
    name: str
    category: str  # 'starter', 'main', 'dessert', 'beverage'
    price: float
    tags: list[str] = []
    available: bool = True


class Customer(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str] = None
    preferences: dict = {}


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None


class Reservation(BaseModel):
    id: int
    customer_id: int
    table_id: int
    date: str
    time: str
    party_size: int
    status: str = "confirmed"


class ReservationCreate(BaseModel):
    customer_id: int
    table_id: int
    date: str
    time: str
    party_size: int


class OrderItem(BaseModel):
    id: int
    reservation_id: int
    menu_item_id: int
    menu_item_name: str
    quantity: int
    price: float


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = 1
