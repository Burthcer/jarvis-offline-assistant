"""Allowed Windows Settings pages; opening a page never changes its settings.
Reference: https://learn.microsoft.com/windows/apps/develop/launch/launch-settings
"""
import re
PAGES={
    'wifi':('Wi-Fi','ms-settings:network-wifi'),
    'bluetooth':('Bluetooth','ms-settings:bluetooth'),
    'sound':('Sound','ms-settings:sound'),
    'display':('Display','ms-settings:display'),
    'network':('Network','ms-settings:network-status'),
    'notifications':('Notifications','ms-settings:notifications'),
    'storage':('Storage','ms-settings:storagesense'),
    'power':('Power','ms-settings:powersleep'),
    'mouse':('Mouse','ms-settings:mousetouchpad'),
    'keyboard':('Keyboard','ms-settings:typing'),
    'apps':('Installed apps','ms-settings:appsfeatures'),
    'default apps':('Default apps','ms-settings:defaultapps'),
    'windows update':('Windows Update','ms-settings:windowsupdate'),
}
ALIASES={'wi fi':'wifi','wireless':'wifi','blue tooth':'bluetooth','audio':'sound','volume':'sound',
         'screen':'display','internet':'network','network and internet':'network','battery':'power',
         'installed apps':'apps','update':'windows update','updates':'windows update'}
def page(words):
    key=' '.join(re.findall(r'[a-z0-9]+',words.lower()))
    return PAGES.get(ALIASES.get(key,key))
