from app.extensions import db

#many-to-many assoc table between item and category
item_category = db.Table('item_category',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)

#many-to-many assoc table between item and provider
item_provider = db.Table('item_provider',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id'), primary_key=True),
    db.Column('provider_id', db.Integer, db.ForeignKey('provider.id'), primary_key=True)
)

# #many-to-many assoc table between requisitions and stock
# requisition_stock = db.Table('requisition_stock',
#     db.Column('requisition_id', db.Integer, db.ForeignKey('requisition.id'), primary_key=True),
#     db.Column('stock_id', db.Integer, db.ForeignKey('stock.id'), primary_key=True)
# )