from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views
from .pwa import service_worker

urlpatterns = [
    path("service-worker.js", service_worker, name="service_worker"),
    # --- DASHBOARD & AUTHENTICATION ---
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # --- WAFANYAKAZI ---
    path('wafanyakazi/', views.wafanyakazi_view, name='wafanyakazi'),
    path('sajili-mfanyakazi/', views.sajili_mfanyakazi, name='sajili_mfanyakazi'),
    path('badili-hali/<int:user_id>/', views.badili_hali_mfanyakazi, name='badili_hali_mfanyakazi'),
    path('futa-mfanyakazi/<int:user_id>/', views.futa_mfanyakazi, name='futa_mfanyakazi'),
    
    # --- KURASA NYINGINEZO ---
    path('wateja/', views.wateja_view, name='wateja'),
    path('wateja/<int:customer_id>/edit/', views.edit_mteja, name='edit_mteja'),
    path('wateja/import/', views.import_customers, name='import_customers'),
    path('mauzo/', views.mauzo_view, name='mauzo'),
    path('receipt/<int:sale_id>/', views.receipt_view, name='receipt'),
    path('receipt/<int:sale_id>/pdf/', views.receipt_pdf, name='receipt_pdf'),
    path('ujumbe/', views.ujumbe_view, name='ujumbe'),
    path('matumizi/', views.matumizi_view, name='matumizi'),
    path('ripoti/', views.ripoti_view, name='ripoti'),
    path('ripoti/daily/', views.daily_report_view, name='daily_report'),
    path('ripoti/daily/pdf/', views.daily_report_pdf, name='daily_report_pdf'),
    path('ripoti/daily/public/<str:token>/pdf/', views.daily_report_pdf_public, name='daily_report_pdf_public'),
    path('stoo/', views.inventory_view, name='stoo_bidhaa'),
    path('stoo/search/', views.product_search_api, name='product_search_api'),
    path('stoo/scan/', views.inventory_scan_api, name='inventory_scan_api'),
    path('stoo/product/<int:product_id>/detail/', views.inventory_product_detail, name='inventory_product_detail'),
    path('stoo/stock-in/', views.inventory_stock_in, name='inventory_stock_in'),
    path('stoo/transfer/', views.inventory_transfer, name='inventory_transfer'),
    path('stoo/adjustment/', views.inventory_adjustment, name='inventory_adjustment'),
    path('stoo/stock-take/', views.inventory_stock_take, name='inventory_stock_take'),
    path('stoo/import/', views.import_products, name='import_products'),
    path('stoo/import-stock/', views.import_stock_to_location, name='import_stock_to_location'),
    path('stoo/phone-scanner/', views.phone_scanner_page, name='phone_scanner_page'),
    path('stoo/phone-scanner/start/', views.phone_scanner_start, name='phone_scanner_start'),
    path('stoo/phone-scanner/poll/', views.phone_scanner_poll, name='phone_scanner_poll'),
    path('stoo/phone-scanner/stop/', views.phone_scanner_stop, name='phone_scanner_stop'),
    path('stoo/phone-scanner/heartbeat/', views.phone_scanner_heartbeat, name='phone_scanner_heartbeat'),
    path('stoo/phone-scanner/scan/', views.phone_scanner_receive, name='phone_scanner_receive'),
    path('stoo/ask/', views.tradecore_inventory_question, name='tradecore_inventory_question'),
    path('stoo/product/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('stoo/product/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('stoo/product/<int:product_id>/barcode/', views.print_product_barcode, name='print_product_barcode'),
    path('stoo/product/<int:product_id>/barcode/regenerate/', views.regenerate_product_barcode, name='regenerate_product_barcode'),
    
    path('sajili-bidhaa/', views.sajili_bidhaa, name='sajili_bidhaa'),
    path('sajili-mteja-haraka/', views.sajili_mteja_haraka, name='sajili_mteja_haraka'), 
    path('upload_profile_picture/', views.upload_profile_picture, name='upload_profile_picture'),
    
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("password_reset_done"),
    ), name="password_reset"),

    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),

    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete"),
    ), name="password_reset_confirm"),

    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),

    
    path("purchase-requests/smart-create/", views.create_smart_reorder_request, name="smart_reorder_create"),
    path("purchase-requests/create/", views.create_purchase_request, name="purchase_request_create"),
    path("purchase-requests/<int:request_id>/approve/", views.approve_purchase_request, name="purchase_request_approve"),
    path("purchase-requests/<int:request_id>/reject/", views.reject_purchase_request, name="purchase_request_reject"),
    path("notifications/<int:notification_id>/read/", views.mark_notification_read, name="notification_mark_read"),
    path("notifications/mark-all-read/", views.mark_all_notifications_read, name="notifications_mark_all_read"),
    path(
        "returns/<int:return_id>/approve/",
        views.approve_sale_return,
        name="sale_return_approve",
    ),
    path(
        "returns/<int:return_id>/reject/",
        views.reject_sale_return,
        name="sale_return_reject",
    ),

    path('control/', views.control_room, name='control_room'),
    path('billing/', views.billing_page, name='billing'),
    path('billing/mobile/initiate/', views.initiate_mobile_payment, name='initiate_mobile_payment'),
    path('billing/mobile/status/', views.mobile_payment_status, name='mobile_payment_status'),
    path('billing/mobile/recheck/', views.recheck_mobile_payment, name='recheck_mobile_payment'),
    path('billing/bank/submit/', views.submit_bank_payment, name='submit_bank_payment'),
    path('billing/flutterwave/webhook/', views.flutterwave_webhook, name='flutterwave_webhook'),
    path('ujumbe/daily-report/settings/', views.daily_report_settings_api, name='daily_report_settings_api'),
    path('ujumbe/whatsapp/send/', views.whatsapp_send_api, name='whatsapp_send_api'),
    path('api/send-daily-report/', views.tuma_daily_report_whatsapp, name='send_daily_report'),

]
