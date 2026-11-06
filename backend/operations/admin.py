from django.contrib import admin
from .models import Client, Contact, Expense, Service, Stop, Transfer, Vehicle

class StopInline(admin.TabularInline): model=Stop; extra=0
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin): list_display=('name','type','date','time','status','client_name','price'); list_filter=('type','status','date','drone'); search_fields=('name','client_name','origin','destination','driver'); inlines=[StopInline]
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin): list_display=('name','kind','email','phone','origin'); search_fields=('name','email','phone')
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin): list_display=('name','kind','person','phone'); list_filter=('kind',); search_fields=('name','person','phone')
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin): list_display=('name','plate','owner','capacity','delegate','status'); list_filter=('owner','status'); search_fields=('name','plate','delegate')
@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin): list_display=('title','datetime','place','responsible','status'); list_filter=('status',); search_fields=('title','place','responsible')
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin): list_display=('concept','category','amount','date','service_name'); list_filter=('category','date'); search_fields=('concept','service_name')
