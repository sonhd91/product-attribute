# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.product.tests.common import TestProductCommon


@tagged("post_install", "-at_install")
class TestProductStatusCase(TestProductCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product = cls.env.ref("product.product_product_13")
        cls.product2 = cls.env.ref("product.product_product_12")
        # To avoid error with filestore and Form test
        cls.product.image_1920 = False

    def test_default(self):
        self.assertEqual(self.product.product_state_id.code, "sellable")

    @freeze_time("2020-09-15")
    def test_new(self):
        self.product.new_until = "2020-09-16"
        self.assertEqual(self.product.state, "new")
        self.assertEqual(self.product.product_state_id.code, "new")
        self.product.new_until = "2020-09-14"
        self.assertEqual(self.product.state, "sellable")
        self.assertEqual(self.product.product_state_id.code, "sellable")

    @freeze_time("2020-09-15")
    def test_discontinued(self):
        self.product.discontinued_until = "2020-09-16"
        self.assertEqual(self.product.state, "discontinued")
        self.assertEqual(self.product.product_state_id.code, "discontinued")
        self.assertEqual(self.product2.state, "sellable")
        self.product.discontinued_until = "2020-09-14"
        self.assertEqual(self.product.state, "sellable")
        self.assertEqual(self.product.product_state_id.code, "sellable")
        self.assertEqual(self.product2.state, "sellable")
        self.product.state = "discontinued"
        self.assertEqual(self.product.product_state_id.code, "discontinued")
        self.assertEqual(self.product2.state, "sellable")
        self.product.state = "new_code"
        self.assertEqual(self.product.product_state_id.code, "new_code")

    @freeze_time("2020-09-15")
    def test_eol(self):
        self.product.end_of_life_date = "2020-09-14"
        self.assertEqual(self.product.state, "endoflife")
        self.assertEqual(self.product.product_state_id.code, "endoflife")
        self.product.end_of_life_date = "2020-09-16"
        self.assertEqual(self.product.state, "phaseout")
        self.assertEqual(self.product.product_state_id.code, "phaseout")

    @freeze_time("2020-09-15")
    def test_priority(self):
        # by order of importance: end_of_life_date, discontinued_until, new_until
        self.product.write(
            {
                "end_of_life_date": "2020-09-14",
                "discontinued_until": "2020-09-16",
                "new_until": "2020-09-16",
            }
        )
        # all set, EOL wins
        self.assertEqual(self.product.state, "endoflife")
        self.assertEqual(self.product.product_state_id.code, "endoflife")
        self.product.end_of_life_date = False
        # discontinued wins
        self.assertEqual(self.product.state, "discontinued")
        self.assertEqual(self.product.product_state_id.code, "discontinued")
        self.product.discontinued_until = False
        self.assertEqual(self.product.state, "new")
        self.assertEqual(self.product.product_state_id.code, "new")

    @freeze_time("2020-09-15")
    def test_onchange(self):
        product = self.env["product.template"].new(
            {
                "name": "Test",
                "type": "test",
            }
        )
        product.new_until = "2020-09-16"
        self.assertEqual(product.state, "new")
        self.assertEqual(product.product_state_id.code, "new")
        product.discontinued_until = "2020-09-16"
        product._onchange_discontinued_until()
        self.assertEqual(product.state, "discontinued")
        self.assertEqual(product.product_state_id.code, "discontinued")
        # new_until wiped
        self.assertEqual(product.state, "discontinued")
        self.assertFalse(product.new_until)
        product.end_of_life_date = "2020-09-14"
        product._onchange_end_of_life_date()
        self.assertEqual(product.state, "endoflife")
        self.assertEqual(product.product_state_id.code, "endoflife")
        # other fields wiped when setting EOL
        self.assertFalse(product.new_until)
        self.assertFalse(product.discontinued_until)

    def test_modified_default_data(self):
        st_env = self.env["product.state"]
        demo_user = self.env.ref("base.user_demo").id
        default_state = st_env._get_module_data()
        vals = {
            "name": "State change",
            "code": "Code change",
            "default": True,
            "active": True,
        }
        for ds_id in default_state:
            vals["code"] = ds_id.code
            with self.assertRaises(ValidationError) as cm:
                st_env.browse(ds_id.id).with_user(demo_user).write(vals)
            wn_expect = cm.exception.args[0]
            self.assertEqual(
                "Cannot delete/modified state installed by module, state name: %s"
                % (ds_id.name),
                wn_expect,
            )
            with self.assertRaises(ValidationError) as cm:
                st_env.browse(ds_id.id).with_user(demo_user).unlink()
            wn_expect = cm.exception.args[0]
            self.assertEqual(
                "Cannot delete/modified state installed by module, state name: %s"
                % (ds_id.name),
                wn_expect,
            )
        # Allow update default value
        current_default_state = st_env.search([("default", "=", True)])
        current_default_state = current_default_state.with_user(demo_user)
        for vals in [
            {"default": False},
            {"active": False},
            {"active": False, "default": False},
        ]:
            self.assertTrue(current_default_state.write(vals))
