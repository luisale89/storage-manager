from app.extensions import db

#many-to-many assoc table between item and provider
item_provider = db.Table('item_provider',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('third_id', db.Integer, db.ForeignKey('third.id'), primary_key=True)
)

#many-to-many assoc table between category and attribute_catalog
attribute_category = db.Table('attribute_category', 
    db.Column('attribute_id', db.Integer, db.ForeignKey('attribute.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)