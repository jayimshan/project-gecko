from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5 import QtNetwork

from bs4 import BeautifulSoup

import requests
import json
import time

import gecko_utils

class Disney(QObject):

	update_status = pyqtSignal(str)
	update_title = pyqtSignal(str)
	update_image = pyqtSignal(str)
	
	request_captcha = pyqtSignal()
	poll_response = pyqtSignal()
 
	headers = {
		'accept': '*/*',
		'accept-encoding': 'gzip, deflate, br',
		'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
		'host': 'www.shopdisney.com',
		'origin': 'https://www.shopdisney.com',
		'pragma': 'no-cache',
		'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0',
		'x-requested-with': 'XMLHttpRequest'
	}
	
	def __init__(self, search, qty, size, color, profile, billing):
		super().__init__()
		self.s = requests.Session()
		self.proxy = None
		self.sku = search
		self.profile = profile
		self.billing = billing

        # Webhook info
		self.store = 'https://www.shopdisney.com/'
		self.title = None
		self.src = None
		self.link = None
		self.price = None
		self.qty = qty
		self.color = color
		self.size = size

		# self.pid = '427245425113'
		self.pid = '465055829394'
		self.qty = '1'
		self.category = 'accessories-women-jewelry+%26+watches'

		self.abort = False
		self.shipmentUUID = None
		self.csrf_token = None
		self.shipping_ID = None
		self.captcha_url = 'https://www.shopdisney.com/checkout?stage=payment#payment'
		self.waiting_for_captcha = False
		self.g_recaptcha_response = None
		self.cookies = []
		self.bearer = None
		self.access_token = None
		self.address_ID = None
		self.order_number = None
		self.commerce_ID = None
		self.payment_ID = None
		self.total_price = None

		self.status = 'Ready'

		self.steps = [
			self.add_to_cart,
			self.validate_basket,
			self.validate_checkout,
			self.start_checkout,
			self.submit_shipping,
			self.captcha,
			self.google_recaptcha,
			self.checkout_validate_basket,
			self.auth_token,
			self.submit_billing,
			self.submit_order,
			self.submit_payment,
			self.get_order,
			self.verify_order,
			self.submit_webhook
		]

	def add_to_cart(self):
		self.status = 'Adding to cart'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://www.shopdisney.com/on/demandware.store/Sites-shopDisney-Site/default/Cart-AddProduct'
		payload = {
			'pid': self.pid,
			'quantity': self.qty,
			'productGuestCategory': self.category
		}
		r = self.s.post(url, headers=self.headers, data=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.shipmentUUID = data['cart']['items'][0]['shipmentUUID']
			print(f'shipmentUUID: {self.shipmentUUID}')
			self.shipping_ID = data['cart']['shipments'][0]['selectedShippingMethod']
			print(f'Shipping ID: {self.shipping_ID}')
			self.title = data['cart']['items'][0]['productName']
			self.price = data['cart']['items'][0]['price']['sales']['formatted']
			self.src = data['cart']['items'][0]['images']['small'][0]['url']
			return True
		else:
			print(r.text)

		self.staus = 'Error carting'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def validate_basket(self):
		self.status = 'Validating basket'
		print(self.status)
		url = 'https://www.shopdisney.com/my-bag?validateBasket=1'
		r = self.s.get(url, headers=self.headers)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			return True

		return False

	def validate_checkout(self):
		self.status = 'Validating checkout'
		print(self.status)
		url = 'https://www.shopdisney.com/ocapi/cc/checkout?validateCheckout=1'
		r = self.s.get(url, headers=self.headers)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			return True

		return False

	def start_checkout(self):
		self.status = 'Starting checkout'
		self.update_status.emit(self.status)
		print(self.status)
		# url = 'https://www.shopdisney.com/checkout'
		url = 'https://www.shopdisney.com/checkout?stage=shipping'
		r = self.s.get(url, headers=self.headers)
		print(r)
		if r.status_code == 200:
			soup = BeautifulSoup(r.text, 'lxml')
			self.csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
			print(f'CSRF TOKEN: {self.csrf_token}')
			return True
		else:
			pass

		self.status = 'Error starting checkout'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def submit_shipping(self):
		self.status = 'Submitting shipping'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://www.shopdisney.com/on/demandware.store/Sites-shopDisney-Site/default/CheckoutShippingServices-SubmitShipping'
		payload = {
			'originalShipmentUUID': self.shipmentUUID,
			'shipmentUUID': self.shipmentUUID,
			'dwfrm_shipping_shippingAddress_addressFields_country': 'US',
			'dwfrm_shipping_shippingAddress_addressFields_firstName': self.profile.first_name,
			'dwfrm_shipping_shippingAddress_addressFields_lastName': self.profile.last_name,
			'dwfrm_shipping_shippingAddress_addressFields_address1': self.profile.shipping_address,
			'dwfrm_shipping_shippingAddress_addressFields_address2': self.profile.shipping_address_2,
			'dwfrm_shipping_shippingAddress_addressFields_postalCode': self.profile.shipping_zip,
			'dwfrm_shipping_shippingAddress_addressFields_city': self.profile.shipping_city,
			'dwfrm_shipping_shippingAddress_addressFields_states_stateCode': self.profile.shipping_state,
			'dwfrm_shipping_shippingAddress_addressFields_phone': self.profile.phone,
			'shippingMethod': self.shipping_ID,
			'csrf_token': self.csrf_token
		}
		r = self.s.post(url, headers=self.headers, data=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.total_price = data['order']['totals']['grandTotalValue']
			print(self.total_price)
			return True
		else:
			print(r.text)

		self.status = 'Error submitting shipping'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def captcha(self):
		self.status = 'Waiting for captcha'
		self.update_status.emit(self.status)
		print(self.status)
		# Save cookies and send with along with emit signal
		self.cookies = []
		for cookie in self.s.cookies:
			c = QtNetwork.QNetworkCookie()
			c.setDomain(cookie.__dict__['domain'])
			c.setName(bytes(cookie.__dict__['name'], 'utf-8'))
			c.setValue(bytes(cookie.__dict__['value'], 'utf-8'))
			self.cookies.append(c)
		# Emit signal to load captcha and browser
		self.request_captcha.emit()
		# self.waiting_for_captcha = True
		# while self.waiting_for_captcha:
		while True:
			if self.abort:
				return False
			else:
				if self.g_recaptcha_response is None:
					print('Waiting for captcha')
					self.poll_response.emit()
					time.sleep(1)
				else:
					return True

	def google_recaptcha(self):
		self.status = 'Google recaptcha'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://www.shopdisney.com/on/demandware.store/Sites-shopDisney-Site/default/Google-reCaptcha'
		payload = {
			'dwfrm_billing_addressFields_firstName': self.profile.first_name,
			'dwfrm_billing_addressFields_lastName': self.profile.last_name,
			'dwfrm_billing_addressFields_address1': self.profile.billing_address,
			'dwfrm_billing_addressFields_address2': self.profile.billing_address_2,
			'dwfrm_billing_addressFields_country': 'US',
			'dwfrm_billing_addressFields_states_stateCode': self.profile.billing_state,
			'dwfrm_billing_addressFields_city': self.profile.billing_city,
			'dwfrm_billing_addressFields_postalCode': self.profile.billing_zip,
			'dwfrm_billing_paymentDetails': '',
			'dwfrm_billing_commerceId': '',
			'dwfrm_billing_vcoWalletRefId': '',
			'dwfrm_billing_creditCardFields_email': self.profile.email,
			'g-recaptcha-response': self.g_recaptcha_response
		}
		h = self.headers
		h['content-type'] = 'application/x-www-form-urlencoded'
		r = self.s.post(url, headers=h, data=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			return True

		self.status = 'Error google recaptcha'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def checkout_validate_basket(self):
		self.status = 'Validating basket'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://www.shopdisney.com/on/demandware.store/Sites-shopDisney-Site/default/Checkout-ValidateBasket'
		payload = {
			'dwfrm_billing_addressFields_firstName': self.profile.first_name,
			'dwfrm_billing_addressFields_lastName': self.profile.last_name,
			'dwfrm_billing_addressFields_address1': self.profile.billing_address,
			'dwfrm_billing_addressFields_address2': self.profile.billing_address_2,
			'dwfrm_billing_addressFields_country': 'US',
			'dwfrm_billing_addressFields_states_stateCode': self.profile.billing_state,
			'dwfrm_billing_addressFields_city': self.profile.billing_city,
			'dwfrm_billing_addressFields_postalCode': self.profile.billing_zip,
			'dwfrm_billing_paymentDetails': '',
			'dwfrm_billing_commerceId': '',
			'dwfrm_billing_vcoWalletRefId': '',
			'dwfrm_billing_creditCardFields_email': self.profile.email,
			'g-recaptcha-response': self.g_recaptcha_response
		}
		h = self.headers
		h['referer'] = 'https://www.shopdisney.com/checkout?stage=payment'
		h['TE'] = 'Trailers'
		r = self.s.post(url, headers=h, data=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.order_number = data['orderID']
			print(f'ORDER ID: {self.order_number}')
			return True

		self.status = 'Error validating basket'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def auth_token(self):
		self.status = 'Auth token'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://authorization.go.com/token'
		payload = {
			'client_id': 'DSI-DISHOPWEB-PROD',
			'grant_type': 'assertion',
			'assertion_type': 'public'
		}
		r = self.s.post(url, headers=self.headers, data=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.access_token = data['access_token']
			self.bearer = data['token_type']
			print(f'ACCESS TOKEN: {self.access_token}')
			return True

		self.status = 'Error auth token'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def submit_billing(self):
		self.status = 'Submitting billing'
		self.update_status.emit(self.status)
		print(self.status)				
		url = 'https://www.shopdisney.com/api/addresses'
		h = self.headers
		h['content-type'] = 'application/json'
		h['Authorization'] = f'{self.bearer} {self.access_token}'
		payload = {
			'addresses': [
				{
					'address1': self.profile.billing_address,
					'address2': self.profile.billing_address_2,
					'city': self.profile.billing_city,
					'country': 'US',
					'first_name': self.profile.first_name,
					'last_name': self.profile.last_name,
					'phone1': self.profile.phone,
					'state': self.profile.billing_state,
					'type': 'SB',
					'zip_code': self.profile.billing_zip
				}
			]
		}
		r = self.s.post(url, headers=h, json=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.address_ID = data['addresses'][0]['address_id']
			self.commerce_ID = data['commerce_id']
			return True
		elif r.status_code == 401:
			self.status = 'Unauthorized'
			self.update_status.emit(self.status)
			print(self.status)
			return False

		self.status = 'Error submitting billing'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def submit_order(self):
		self.status = 'Submitting order'
		self.update_status.emit(self.status)
		print(self.status)
		url = 'https://www.shopdisney.com/api/orders'
		h = self.headers
		h['commerce_id'] = self.commerce_ID
		h['authorization'] = f'{self.bearer} {self.access_token}'
		h['content-type'] = 'application/json'
		payload = {
			'orders': [{
				'description': 'GUEST|BAG',
				'ext_order_id': self.order_number
			}]
		}
		r = self.s.post(url, headers=h, json=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.commerce_ID = data['commerce_id']
			self.order_ID = data['orders'][0]['order_id']
			return True

		self.status = 'Error submitting order'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def submit_payment(self):
		self.status = 'Submitting payment'
		self.update_status.emit(self.status)
		print(self.status)
		url = f'https://www.shopdisney.com/api/orders/{self.order_ID}/payments'
		h = self.headers
		h['commerce_id'] = self.commerce_ID
		h['authorization'] = f'{self.bearer} {self.access_token}'
		h['content-type'] = 'application/json'
		# payload = {
		# 	'payments': [{
		# 		'address': {
		# 			'address_id': self.address_ID
		# 		},
		# 		'card_brand': 'VS',
		# 		'card_number': self.billing.card_number,
		# 		'expiration_month': self.billing.exp_month,
		# 		'expiration_year': self.billing.exp_year,
		# 		'is_expired': False,
		# 		'name_holder': self.billing.name_on_card,
		# 		'payment_id': '',
		# 		'security_code': self.billing.cvv,
		# 		'type': 'CC'
		# 	}]
		# }
		payload = {
			'payments': [{
				'address': {
					'address_id': self.address_ID
				},
				'card_brand': 'VS',
				'card_number': '4767718266910894',
				'expiration_month': '4',
				'expiration_year': '2026',
				'is_expired': False,
				'name_holder': 'Jamie Lee',
				'payment_id': '',
				'security_code': '799',
				'type': 'CC'
			}]
		}
		r = self.s.post(url, headers=h, json=payload)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.commerce_ID = data['commerce_id']
			self.payment_ID = data['payments'][0]['payment_id']
			return True

		self.status = 'Error submitting payment'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def get_order(self):
		self.status = 'Getting order'
		self.update_status.emit(self.status)
		print(self.status)
		url = f'https://www.shopdisney.com/api/orders/{self.order_ID}'
		h = self.headers
		h['commerce_id'] = self.commerce_ID
		h['authorization'] = f'{self.bearer} {self.access_token}'
		h['content-type'] = 'application/json'
		r = self.s.get(url, headers=h)
		print(r)
		if r.status_code == 200:
			data = r.json()
			print(data)
			self.commerce_ID = data['commerceId']
			return True

		self.status = 'Error getting order'
		self.update_status.emit(self.status)
		print(self.status)
		return False

	def verify_order(self):
		self.status = f'Veryifing order: {self.order_number}'
		self.update_status.emit(self.status)
		print(self.status)
		url = f'https://www.shopdisney.com/api/v2/orders/{self.order_number}'
		h = self.headers
		h['commerce_id'] = self.commerce_ID
		h['authorization'] = f'{self.bearer} {self.access_token}'
		h['content-type'] = 'application/json'
		payload = {
			'orders': [{
				# 'order_total': self.total_price,
				'order_total': '22.20',
				'payments': [{
					'payment_id': self.payment_ID,
					# 'security_code': self.billing.cvv,
					'security_code': '799',
					'type': 'CC'
				}]
			}]
		}
		r = self.s.post(url, headers=h, json=payload)
		print(r)
		data = r.json()
		print(data)
		return True

	def submit_webhook(self):
		try:
			gecko_utils.post_webhook(self.title, self.store, self.link, self.price, self.src)
		except Exception as e:
			print('Error posting webhook')
			print(f'{e}')

		return True