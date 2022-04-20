from app.extensions import db

#many-to-many assoc table between item and provider
item_provider = db.Table('item_provider',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('provider_id', db.Integer, db.ForeignKey('provider.id'), primary_key=True)
)

#many-to-many assoc table between category and attribute_catalog
attribute_category = db.Table('attribute_category', 
    db.Column('attribute_catalog_id', db.Integer, db.ForeignKey('attribute_catalog.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)

#M2M assoc table between Adquisition and Inventory
adquisition_inventory = db.Table('adquisition_category', 
    db.Column('adquisition_id', db.Integer, db.ForeignKey('adquisition.id'), primary_key=True),
    db.Column('inventory_id', db.Integer, db.ForeignKey('inventory.id'), primary_key=True)
)