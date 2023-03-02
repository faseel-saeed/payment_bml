# Faseel Saeed

{
    'name': "Payment Provider: BML",
    'version': '0.1.0',
    'author': 'Benlever Pvt Ltd',
    'website': 'https://www.benlever.com',
    'category': 'Accounting/Payment Providers',
    'sequence': 351,
    'summary': "Payment provider by BML (MPGS)",
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_bml_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    
    
}
