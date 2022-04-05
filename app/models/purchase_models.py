from app.extensions import db
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class Purchase(db.Model):
    __tablename__ = 'purchase'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text)
    private_request = db.Column(db.Boolean)
    purchase_order_historics = db.Column(JSON)
    quotation_historics = db.Column(JSON)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    #relations
    storage = db.relationship('Storage', back_populates='purchases', lazy='select')
    provider = db.relationship('Provider', back_populates='purchases', lazy='select')
    items_purchase = db.relationship('ItemPurchase', back_populates='purchase', lazy='select')
    quotations = db.relationship('Quotation', back_populates='purchase', lazy='select')

    def __repr__(self) -> str:
        return f'<purchase_id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'description': self.description,
            'private_request': self.private_request,
            'purchase_order_historics': self.purchase_order_historics,
            'quotation_historics': self.quotation_historics
        }


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_order'
    id = db.Column(db.Integer, primary_key=True)
    po_code = db.Column(db.String(128), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotation.id'), nullable=False)
    #relations
    stock = db.relationship('Stock', back_populates='purchase_order', uselist=False, lazy='select')
    quotation = db.relationship('Quotation', back_populates='purchase_order', lazy='select')

    def __repr__(self) -> str:
        return f'<Purchase Order id: {self.id}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'po_code': self.po_code,
            'date_created': self.date_created
        }


class Quotation(db.Model):
    __tablename__ = 'quotation'
    id = db.Column(db.Integer, primary_key=True)
    quote_code = db.Column(db.String(128), nullable=False)
    quote_review = db.Column(JSON)
    order_complete = db.Column(db.Boolean)
    order_logs = db.Column(JSON)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    item_purchase_id = db.Column(db.Integer, db.ForeignKey('item_purchase.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'), nullable=False)
    #relations
    purchase = db.relationship('Purchase', back_populates='quotations', lazy='select')
    item_purchase = db.relationship('ItemPurchase', back_populates='quotations', lazy='select')
    provider = db.relationship('Provider', back_populates='quotations', lazy='select')
    purchase_order = db.relationship('PurchaseOrder', back_populates='quotation', uselist=False ,lazy='select')

    def __repr__(self) -> str:
        return f'<Quotation id: {self.id}>'

    def serialize(self):
        return {
            'id': self.id,
            'quote_code': self.quote_code,
            'quote_review': self.quote_review,
            'order_complete': self.order_complete,
            'order_logs': self.order_logs
        }


class ItemPurchase(db.Model):
    __tablename__ = 'item_purchase'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text)
    item_quantity = db.Column(db.Float())
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    #relations
    purchase = db.relationship('Purchase', back_populates='items_purchase', lazy='select')
    item = db.relationship('Item', back_populates='item_purchases', lazy='select')
    quotations = db.relationship('Quotation', back_populates='item_purchase', lazy='select')

    def __repr__(self) -> str:
        return f'<Item-Quote Request id: {self.id}>'

    def serialize(self):
        return {
            'id': self.id,
            'description': self.description,
            'item_quantity': self.item_quantity
        }