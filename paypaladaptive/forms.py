'''
Base forms for user-interaction and payments

Created on Jun 14, 2011

@author: greg
'''
from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, to_locale, get_language
import settings

def paypal_image_url(type='pay'):
    '''
    Due to the way Paypal supports localization, we can't ask for a valid two character locale.
    So if our locale is such a one we'll have to modify it to fit Paypal's expectations.
    
    eg: 'en' -> 'en_US'
    '''
    current_locale = to_locale(get_language())
    if current_locale.find('_') == -1:
        current_locale = "%s_%s" % (current_locale, 
                                    current_locale.upper() if current_locale != 'en' else 'US')

    if type == 'pay':
        return 'https://www.paypal.com/%s/i/btn/btn_dg_pay_w_paypal.gif' % current_locale
    
    raise ValueError('Unknown image type')
 
    
class PayPalAdaptiveEmbeddedForm(forms.Form):
    """
    Form used to provide access to an embedded checkout form from Paypal.
    
    You must provide the form with a valid paykey from the Pay API operation.
    """
    expType = forms.CharField(initial='light', widget=forms.HiddenInput)
    payKey = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, paykey, submit_title=_(u'Pay with Paypal'), *args, **kwargs):
        super(PayPalAdaptiveEmbeddedForm, self).__init__(*args, **kwargs)
        self.auto_id = '%s'
        self.initial['payKey'] = paykey
        self.submit_title = submit_title

    def render(self):
        
        return mark_safe(u"""
            <form action="%(action)s" target="PPDGFrame">
                %(form)s
                <input type="image" id="submitBtn" src="%(image_url)s" alt="%(submit_title)s" />
            </form>
            <script type="text/javascript">
                var dgFlow;
                window.onload = function() {
                    dgFlow = new PAYPAL.apps.DGFlow({ trigger: 'submitBtn' });
                } 
            </script>
            """ % {'action': settings.EMBEDDED_ENDPOINT,
                   'form': self.as_p(),
                   'image_url': paypal_image_url(),
                   'submit_title': self.submit_title})

    class Media:
        js = ('http://www.paypalobjects.com/js/external/dg.js',)
        
class PayPalAdaptiveEmbeddedPreapprovalForm(forms.Form):
    """
    Form used to provide access to an embedded checkout form from Paypal.
    
    You must provide the form with a valid preapproval from the Pay API operation.
    """
    expType = forms.CharField(initial='light', widget=forms.HiddenInput)
    preapprovalKey = forms.CharField(widget=forms.HiddenInput)
    _cmd = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, preapprovalkey, submit_title=_(u'Pay with Paypal'), *args, **kwargs):
        super(PayPalAdaptiveEmbeddedPreapprovalForm, self).__init__(*args, **kwargs)
        self.auto_id = '%s'
        self.initial['preapprovalKey'] = preapprovalkey
        self.submit_title = submit_title
        self.initial['_cmd'] = "_ap-preapproval"

    def render(self):
        
        return mark_safe(u"""
            <form action="%(action)s" target="PPDGFrame">
                %(form)s
                <input type="image" id="submitBtn" src="%(image_url)s" alt="%(submit_title)s" />
            </form>
            <script type="text/javascript">
                var dgFlow;
                window.onload = function() {
                    dgFlow = new PAYPAL.apps.DGFlow({ trigger: 'submitBtn' });
                } 
            </script>
            """ % {'action': settings.EMBEDDED_ENDPOINT,
                   'form': self.as_p(),
                   'image_url': paypal_image_url(),
                   'submit_title': self.submit_title})

    class Media:
        js = ('http://www.paypalobjects.com/js/external/dg.js',)