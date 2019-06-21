from hs_core.hydroshare import resource
from django.test.testcases import TestCase

from django.contrib.auth.models import Group

from hs_core.hydroshare import users
from django_irods.storage import IrodsStorage

class TestStorage(TestCase):
	def setUp(self):
		super(TestStorage, self).setUp()
		self.group, _ = Group.objects.get_or_create(name="Hydroshare Author")
		self.user = users.create_account(
			'test_user@gmail.com', username='testuser', first_name='Manish', last_name='Aryal', superuser=False )
		self.rtype='CompositeResource'
		self.title='My title'
		self.res= resource.create_resource(self.rtype, self.user, self.title)
		self.pid = self.res.short_id

	def tearDown(self):
		resource.delete_resource(self.pid)
		self.group.delete()
		self.user.delete()

	def test1(self):
		print('Test1')
