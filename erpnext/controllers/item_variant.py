# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import copy
import json

import requests

import frappe
from frappe import _
from frappe.utils import cstr, flt

from erpnext.utilities.product import get_item_codes_by_attributes


class ItemVariantExistsError(frappe.ValidationError):
	pass


class InvalidItemAttributeValueError(frappe.ValidationError):
	pass


class ItemTemplateCannotHaveStock(frappe.ValidationError):
	pass



def log_item_changes(doc, method):
    """Log all values of Item and highlight changes"""

    if doc.flags.in_insert:
        return  # New item creation; no comparison needed

    old_doc = doc.get_doc_before_save()
    if not old_doc:
        print("⚠️ No old doc found for comparison")
        return

    import requests  # Ensure you have this imported at the top

    item_name = doc.get("item_name")
    tpin = 18288282828
    bhfId = "0000"

    # Get country code
    orgnNatCd = doc.get("custom_origin_place_code")
    try:
        response = requests.get(f"http://192.168.1.146:9010/country/{orgnNatCd}/", timeout=5)
        response.raise_for_status()
        country_data = response.json()
        country_code = country_data.get("code")
        if not country_code:
            frappe.throw(f"Country code not found in API response for '{orgnNatCd}'.")
    except requests.RequestException as e:
        frappe.throw(f"Failed to get country code for '{orgnNatCd}': {e}")

    # Get product type and convert to item type code
    product_type = doc.get("custom_product_type")
    itemTyCd = {"Raw Material": "1", "Finished Product": "2"}.get(product_type, "3")

    # Get packaging unit code
    pkgUnitCd = doc.get("custom_packaging_unit_code")
    try:
        response = requests.get(f"http://192.168.1.146:9010/packaging-unit-code/{pkgUnitCd}/", timeout=5)
        response.raise_for_status()
        packaging_data = response.json()
        packaging_unit_code = packaging_data.get("code")
        if not packaging_unit_code:
            frappe.throw(f"Packaging unit code not found for '{pkgUnitCd}'.")
    except requests.RequestException as e:
        frappe.throw(f"Failed to get packaging unit code for '{pkgUnitCd}': {e}")

    # Get quantity unit of measure code
    qtyUnitCd = doc.get("custom_units_of_measure")
    try:
        unit_response = requests.get(f"http://192.168.1.146:9010/unitofmeasure/{qtyUnitCd}/", timeout=5)
        unit_response.raise_for_status()
        unit_data = unit_response.json()
        qty_unit_code = unit_data.get("code")
        if not qty_unit_code:
            frappe.throw("Error Getting Quantity unit code.")
    except requests.RequestException as e:
        frappe.throw(f"Failed to get unit code for '{qtyUnitCd}': {e}")

    # Get VAT category code
    vatCatCd = doc.get("custom_vat")
    vat_code_map = {
        "StandardRated": "A",
        "MinimumTaxableValue": "B",
        "Exports": "C1",
        "ZeroRatingLocalPurchases": "C2",
        "ZeroRatedByNature": "C3",
        "Exempt": "D",
        "Disbursement": "E",
        "ReverseVAT": "RVAT"
    }
    vatCatCd_code = vat_code_map.get(vatCatCd)
    if not vatCatCd_code:
        frappe.throw(f"Invalid or unmapped VAT category: '{vatCatCd}'")

    # Other values
    iplCatCd = doc.get("custom_ipl_category_code")
    tlCatCd = doc.get("custom_tl_category_code")
    exciseTxCatCd = doc.get("custom_excise_tax_category_code")
    useYn = doc.get("custom_used__unused")
    modrNm = doc.get("owner")
    modrId = doc.get("owner")
    regrId = doc.get("owner")

    print("🛒 Item Details:")
    print(f"Item Name       : {item_name}")
    print(f"TPIN            : {tpin}")
    print(f"BHF ID          : {bhfId}")
    print(f"Origin Code     : {country_code} ")
    print(f"Item Type Code  : {itemTyCd}")
    print(f"Package Unit    : {packaging_unit_code}")
    print(f"Quantity Unit   : {qty_unit_code} ")
    print(f"VAT Category    : {vatCatCd_code}")
    print(f"IPL Category    : {iplCatCd}")
    print(f"TL Category     : {tlCatCd}")
    print(f"Excise Tax Cat  : {exciseTxCatCd}")
    print(f"Use (Y/N)       : {useYn}")
    print(f"Modified by     : {modrNm}")
    print(f"Registered ID   : {regrId}")

	
@frappe.whitelist()
def test_item_logging():
    item = frappe.get_doc("Item", "ITEM-001")
    item.save()
    return "Test executed"
@frappe.whitelist()
def get_variant(template, args=None, variant=None, manufacturer=None, manufacturer_part_no=None):
	"""
	Validates Attributes and their Values, then looks for an exactly
	matching Item Variant

	:param item: Template Item
	:param args: A dictionary with "Attribute" as key and "Attribute Value" as value
	"""
	item_template = frappe.get_doc("Item", template)

	if item_template.variant_based_on == "Manufacturer" and manufacturer:
		return make_variant_based_on_manufacturer(item_template, manufacturer, manufacturer_part_no)

	if isinstance(args, str):
		args = json.loads(args)

	attribute_args = {k: v for k, v in args.items() if k != "use_template_image"}
	if not attribute_args:
		frappe.throw(_("Please specify at least one attribute in the Attributes table"))

	return find_variant(template, args, variant)


def make_variant_based_on_manufacturer(template, manufacturer, manufacturer_part_no):
	"""Make and return a new variant based on manufacturer and
	manufacturer part no"""
	from frappe.model.naming import append_number_if_name_exists

	variant = frappe.new_doc("Item")

	copy_attributes_to_variant(template, variant)

	variant_name = f"{template.name} - {manufacturer}"
	if manufacturer_part_no:
		variant_name += f" - {manufacturer_part_no}"

	variant.item_code = append_number_if_name_exists("Item", variant_name)
	variant.flags.ignore_mandatory = True
	variant.save()

	if not frappe.db.exists("Item Manufacturer", {"item_code": variant.name, "manufacturer": manufacturer}):
		manufacturer_doc = frappe.new_doc("Item Manufacturer")
		manufacturer_doc.update(
			{
				"item_code": variant.name,
				"manufacturer": manufacturer,
				"manufacturer_part_no": manufacturer_part_no,
			}
		)

		manufacturer_doc.flags.ignore_mandatory = True
		manufacturer_doc.save(ignore_permissions=True)

	return variant


def validate_item_variant_attributes(item, args=None):
	if isinstance(item, str):
		item = frappe.get_doc("Item", item)

	if not args:
		args = {d.attribute.lower(): d.attribute_value for d in item.attributes}

	attribute_values, numeric_values = get_attribute_values(item)

	for attribute, value in args.items():
		if not value:
			continue

		if attribute.lower() in numeric_values:
			numeric_attribute = numeric_values[attribute.lower()]
			validate_is_incremental(numeric_attribute, attribute, value, item.name)

		else:
			attributes_list = attribute_values.get(attribute.lower(), [])
			validate_item_attribute_value(attributes_list, attribute, value, item.name, from_variant=True)


def validate_is_incremental(numeric_attribute, attribute, value, item):
	from_range = numeric_attribute.from_range
	to_range = numeric_attribute.to_range
	increment = numeric_attribute.increment

	if increment == 0:
		# defensive validation to prevent ZeroDivisionError
		frappe.throw(_("Increment for Attribute {0} cannot be 0").format(attribute))

	is_in_range = from_range <= flt(value) <= to_range
	precision = max(len(cstr(v).split(".")[-1].rstrip("0")) for v in (value, increment))
	# avoid precision error by rounding the remainder
	remainder = flt((flt(value) - from_range) % increment, precision)

	is_incremental = remainder == 0 or remainder == increment

	if not (is_in_range and is_incremental):
		frappe.throw(
			_(
				"Value for Attribute {0} must be within the range of {1} to {2} in the increments of {3} for Item {4}"
			).format(attribute, from_range, to_range, increment, item),
			InvalidItemAttributeValueError,
			title=_("Invalid Attribute"),
		)


def validate_item_attribute_value(attributes_list, attribute, attribute_value, item, from_variant=True):
	allow_rename_attribute_value = frappe.db.get_single_value(
		"Item Variant Settings", "allow_rename_attribute_value"
	)
	if allow_rename_attribute_value:
		pass
	elif attribute_value not in attributes_list:
		if from_variant:
			frappe.throw(
				_("{0} is not a valid Value for Attribute {1} of Item {2}.").format(
					frappe.bold(attribute_value), frappe.bold(attribute), frappe.bold(item)
				),
				InvalidItemAttributeValueError,
				title=_("Invalid Value"),
			)
		else:
			msg = _("The value {0} is already assigned to an existing Item {1}.").format(
				frappe.bold(attribute_value), frappe.bold(item)
			)
			msg += "<br>" + _(
				"To still proceed with editing this Attribute Value, enable {0} in Item Variant Settings."
			).format(frappe.bold(_("Allow Rename Attribute Value")))

			frappe.throw(msg, InvalidItemAttributeValueError, title=_("Edit Not Allowed"))


def get_attribute_values(item):
	if not frappe.flags.attribute_values:
		attribute_values = {}
		numeric_values = {}
		for t in frappe.get_all("Item Attribute Value", fields=["parent", "attribute_value"]):
			attribute_values.setdefault(t.parent.lower(), []).append(t.attribute_value)

		for t in frappe.get_all(
			"Item Variant Attribute",
			fields=["attribute", "from_range", "to_range", "increment"],
			filters={"numeric_values": 1, "parent": item.variant_of},
		):
			numeric_values[t.attribute.lower()] = t

		frappe.flags.attribute_values = attribute_values
		frappe.flags.numeric_values = numeric_values

	return frappe.flags.attribute_values, frappe.flags.numeric_values


def find_variant(template, args, variant_item_code=None):
	possible_variants = [i for i in get_item_codes_by_attributes(args, template) if i != variant_item_code]

	for variant in possible_variants:
		variant = frappe.get_doc("Item", variant)

		if len(args.keys()) == len(variant.get("attributes")):
			# has the same number of attributes and values
			# assuming no duplication as per the validation in Item
			match_count = 0

			for attribute, value in args.items():
				for row in variant.attributes:
					if row.attribute == attribute and row.attribute_value == cstr(value):
						# this row matches
						match_count += 1
						break

			if match_count == len(args.keys()):
				return variant.name


@frappe.whitelist()
def create_variant(item, args, use_template_image=False):
	use_template_image = frappe.parse_json(use_template_image)
	if isinstance(args, str):
		args = json.loads(args)

	template = frappe.get_doc("Item", item)
	variant = frappe.new_doc("Item")
	variant.variant_based_on = "Item Attribute"
	variant_attributes = []

	for d in template.attributes:
		variant_attributes.append({"attribute": d.attribute, "attribute_value": args.get(d.attribute)})

	variant.set("attributes", variant_attributes)
	copy_attributes_to_variant(template, variant)

	if use_template_image and template.image:
		variant.image = template.image

	make_variant_item_code(template.item_code, template.item_name, variant)

	return variant


@frappe.whitelist()
def enqueue_multiple_variant_creation(item, args, use_template_image=False):
	use_template_image = frappe.parse_json(use_template_image)
	# There can be innumerable attribute combinations, enqueue
	if isinstance(args, str):
		variants = json.loads(args)
	total_variants = 1
	for key in variants:
		total_variants *= len(variants[key])
	if total_variants >= 600:
		frappe.throw(_("Please do not create more than 500 items at a time"))
		return
	if total_variants < 10:
		return create_multiple_variants(item, args, use_template_image)
	else:
		frappe.enqueue(
			"erpnext.controllers.item_variant.create_multiple_variants",
			item=item,
			args=args,
			use_template_image=use_template_image,
			now=frappe.in_test,
		)
		return "queued"


def create_multiple_variants(item, args, use_template_image=False):
	count = 0
	if isinstance(args, str):
		args = json.loads(args)

	template_item = frappe.get_doc("Item", item)
	args_set = generate_keyed_value_combinations(args)

	for attribute_values in args_set:
		if not get_variant(item, args=attribute_values):
			variant = create_variant(item, attribute_values)
			if use_template_image and template_item.image:
				variant.image = template_item.image
			variant.save()
			count += 1

	return count


def generate_keyed_value_combinations(args):
	"""
	From this:

	        args = {"attr1": ["a", "b", "c"], "attr2": ["1", "2"], "attr3": ["A"]}

	To this:

	        [
	                {u'attr1': u'a', u'attr2': u'1', u'attr3': u'A'},
	                {u'attr1': u'b', u'attr2': u'1', u'attr3': u'A'},
	                {u'attr1': u'c', u'attr2': u'1', u'attr3': u'A'},
	                {u'attr1': u'a', u'attr2': u'2', u'attr3': u'A'},
	                {u'attr1': u'b', u'attr2': u'2', u'attr3': u'A'},
	                {u'attr1': u'c', u'attr2': u'2', u'attr3': u'A'}
	        ]

	"""
	# Return empty list if empty
	if not args:
		return []

	# Turn `args` into a list of lists of key-value tuples:
	# [
	# 	[(u'attr2', u'1'), (u'attr2', u'2')],
	# 	[(u'attr3', u'A')],
	# 	[(u'attr1', u'a'), (u'attr1', u'b'), (u'attr1', u'c')]
	# ]
	key_value_lists = [[(key, val) for val in args[key]] for key in args.keys()]

	# Store the first, but as objects
	# [{u'attr2': u'1'}, {u'attr2': u'2'}]
	results = key_value_lists.pop(0)
	results = [{d[0]: d[1]} for d in results]

	# Iterate the remaining
	# Take the next list to fuse with existing results
	for l in key_value_lists:
		new_results = []
		for res in results:
			for key_val in l:
				# create a new clone of object in result
				obj = copy.deepcopy(res)
				# to be used with every incoming new value
				obj[key_val[0]] = key_val[1]
				# and pushed into new_results
				new_results.append(obj)
		results = new_results

	return results


def copy_attributes_to_variant(item, variant):
	# copy non no-copy fields

	exclude_fields = [
		"naming_series",
		"item_code",
		"item_name",
		"published_in_website",
		"opening_stock",
		"variant_of",
		"valuation_rate",
	]

	if item.variant_based_on == "Manufacturer":
		# don't copy manufacturer values if based on part no
		exclude_fields += ["manufacturer", "manufacturer_part_no"]

	allow_fields = [d.field_name for d in frappe.get_all("Variant Field", fields=["field_name"])]
	if "variant_based_on" not in allow_fields:
		allow_fields.append("variant_based_on")
	for field in item.meta.fields:
		# "Table" is part of `no_value_field` but we shouldn't ignore tables
		if (field.reqd or field.fieldname in allow_fields) and field.fieldname not in exclude_fields:
			if variant.get(field.fieldname) != item.get(field.fieldname):
				if field.fieldtype == "Table":
					variant.set(field.fieldname, [])
					for d in item.get(field.fieldname):
						row = copy.deepcopy(d)
						if row.get("name"):
							row.name = None
						variant.append(field.fieldname, row)
				else:
					variant.set(field.fieldname, item.get(field.fieldname))

	variant.variant_of = item.name

	if "description" not in allow_fields:
		if not variant.description:
			variant.description = ""
	else:
		if item.variant_based_on == "Item Attribute":
			if variant.attributes:
				attributes_description = item.description + " "
				for d in variant.attributes:
					attributes_description += (
						"<div>" + d.attribute + ": " + cstr(d.attribute_value) + "</div>"
					)

				if attributes_description not in variant.description:
					variant.description = attributes_description


def make_variant_item_code(template_item_code, template_item_name, variant):
	"""Uses template's item code and abbreviations to make variant's item code"""
	if variant.item_code:
		return

	abbreviations = []
	for attr in variant.attributes:
		item_attribute = frappe.db.sql(
			"""select i.numeric_values, v.abbr
			from `tabItem Attribute` i left join `tabItem Attribute Value` v
				on (i.name=v.parent)
			where i.name=%(attribute)s and (v.attribute_value=%(attribute_value)s or i.numeric_values = 1)""",
			{"attribute": attr.attribute, "attribute_value": attr.attribute_value},
			as_dict=True,
		)

		if not item_attribute:
			continue
			# frappe.throw(_('Invalid attribute {0} {1}').format(frappe.bold(attr.attribute),
			# 	frappe.bold(attr.attribute_value)), title=_('Invalid Attribute'),
			# 	exc=InvalidItemAttributeValueError)

		abbr_or_value = (
			cstr(attr.attribute_value) if item_attribute[0].numeric_values else item_attribute[0].abbr
		)
		abbreviations.append(abbr_or_value)

	if abbreviations:
		variant.item_code = "{}-{}".format(template_item_code, "-".join(abbreviations))
		variant.item_name = "{}-{}".format(template_item_name, "-".join(abbreviations))


@frappe.whitelist()
def create_variant_doc_for_quick_entry(template, args):
	variant_based_on = frappe.db.get_value("Item", template, "variant_based_on")
	args = json.loads(args)
	if variant_based_on == "Manufacturer":
		variant = get_variant(template, **args)
	else:
		existing_variant = get_variant(template, args)
		if existing_variant:
			return existing_variant
		else:
			variant = create_variant(template, args=args)
			variant.name = variant.item_code
			validate_item_variant_attributes(variant, args)
	return variant.as_dict()