from app.extensions import db

#many-to-many assoc table between item and provider
item_provider = db.Table('item_provider',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('provider_id', db.Integer, db.ForeignKey('provider.id'), primary_key=True)
)

#many-to-many assoc table between category and attribute_catalog
attribute_category = db.Table('attribute_category', 
    db.Column('attribute_id', db.Integer, db.ForeignKey('attribute.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)

#many-to-many assoc table between Attribute_value and Item
attributeValue_item = db.Table('attributeValue_item',
    db.Column('attribute_value_id', db.Integer, db.ForeignKey('attribute_value.id'), primary_key=True),
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True)
)