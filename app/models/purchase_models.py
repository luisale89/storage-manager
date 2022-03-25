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
    #relations

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
    #relations

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
    #relations

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


class ItemQuoteRequest(db.Model):
    __tablename__ = 'item_quoterequest'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text)
    item_quantity = db.Column(db.Float())
    #relations

    def __repr__(self) -> str:
        return f'<Item-Quote Request id: {self.id}>'

    def serialize(self):
        return {
            'id': self.id,
            'description': self.description,
            'item_quantity': self.item_quantity
        }