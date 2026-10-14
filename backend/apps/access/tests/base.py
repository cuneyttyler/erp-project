"""A tenant test base that builds the tenant schema once per test run
instead of once per test class.

django-tenants' TenantTestCase creates a schema and runs every migration in
each class's setUpClass -- tens of seconds per class on this project.
FastTenantTestCase reuses one schema, with each test still isolated in its
own rolled-back transaction, but as shipped it has a flaw this subclass
fixes: the `SET search_path` that points the connection at the tenant schema
is issued lazily, at the first query -- which is inside the first test's
transaction, so it is rolled back with that test and every later test in the
class runs against the public schema ("relation core_user does not exist").
Issuing one query in setUpClass applies the search path outside any test
transaction, where it sticks.
"""

from django.db import connection
from django_tenants.test.cases import FastTenantTestCase

# The domain FastTenantTestCase registers; requests must be made to it for
# the tenant middleware to resolve the test tenant.
HOST = {"HTTP_HOST": "tenant.fast-test.com"}


class SharedTenantTestCase(FastTenantTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
