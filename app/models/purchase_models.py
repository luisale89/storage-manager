from app.extensions import db
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class QuoteRequest(db.Model):
    __tablename__ = 'quote_request'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text)
    private_request = db.Column(db.Boolean)
    purchase_order_historics = db.Column(JSON)
    quotation_historics = db.Column(JSON)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    #relations
    storage = db.relationship('Storage', back_populates='quote_requests', lazy='select')
    provider = db.relationship('Provider', back_populates='quote_requests', lazy='select')
    purchase_orders = db.relationship('PurchaseOrder', back_populates='quote_request', lazy='select')
    item_quotes = db.relationship('ItemQuote', back_populates='quote_request', lazy='select')

    def __repr__(self) -> str:
        return f'<Quote_Request_id: {self.id}>'

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
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_request.id'), nullable=False)
    #relations
    stocks = db.relationship('Stock', back_populates='purchase_order', lazy='select')
    quote_request = db.relationship('QuoteRequest', back_populates='purchase_orders', lazy='select')
    quotations = db.relationship('Quotation', back_populates='purchase_order', lazy='select')

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
    item_quote_id = db.Column(db.Integer, db.ForeignKey('item_quote.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'), nullable=False)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'))
    #relations
    item_quote = db.relationship('ItemQuote', back_populates='quotations', lazy='select')
    provider = db.relationship('Provider', back_populates='quotations', lazy='select')
    purchase_order = db.relationship('PurchaseOrder', back_populates='quotations', lazy='select')

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


class ItemQuote(db.Model):
    __tablename__ = 'item_quote'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text)
    item_quantity = db.Column(db.Float())
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_request.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    #relations
    quote_request = db.relationship('QuoteRequest', back_populates='item_quotes', lazy='select')
    item = db.relationship('Item', back_populates='item_quotes', lazy='select')
    quotations = db.relationship('Quotation', back_populates='item_quote', lazy='select')

    def __repr__(self) -> str:
        return f'<Item-Quote Request id: {self.id}>'

    def serialize(self):
        return {
            'id': self.id,
            'description': self.description,
            'item_quantity': self.item_quantity
        }