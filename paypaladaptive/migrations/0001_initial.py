# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Payment'
        db.create_table('paypaladaptive_payment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('amount_currency', self.gf('money.contrib.django.models.fields.CurrencyField')(default=None, max_length=3)),
            ('amount', self.gf('money.contrib.django.models.fields.MoneyField')(default=None, max_digits=6, decimal_places=2, blank=True)),
            ('created_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('secret_uuid', self.gf('paypaladaptive.models.UUIDField')(max_length=32)),
            ('debug_request', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('debug_response', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('purchaser', self.gf('django.db.models.fields.related.ForeignKey')(related_name='payments_made', to=orm['auth.User'])),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='payments_received', null=True, to=orm['auth.User'])),
            ('pay_key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('transaction_id', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=10)),
            ('status_detail', self.gf('django.db.models.fields.CharField')(max_length=2048)),
        ))
        db.send_create_signal('paypaladaptive', ['Payment'])

        # Adding model 'Refund'
        db.create_table('paypaladaptive_refund', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('amount_currency', self.gf('money.contrib.django.models.fields.CurrencyField')(default=None, max_length=3)),
            ('amount', self.gf('money.contrib.django.models.fields.MoneyField')(default=None, max_digits=6, decimal_places=2, blank=True)),
            ('created_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('secret_uuid', self.gf('paypaladaptive.models.UUIDField')(max_length=32)),
            ('debug_request', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('debug_response', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('payment', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['paypaladaptive.Payment'], unique=True)),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=10)),
            ('status_detail', self.gf('django.db.models.fields.CharField')(max_length=2048)),
        ))
        db.send_create_signal('paypaladaptive', ['Refund'])

        # Adding model 'Preapproval'
        db.create_table('paypaladaptive_preapproval', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('amount_currency', self.gf('money.contrib.django.models.fields.CurrencyField')(default=None, max_length=3)),
            ('amount', self.gf('money.contrib.django.models.fields.MoneyField')(default=None, max_digits=6, decimal_places=2, blank=True)),
            ('created_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('secret_uuid', self.gf('paypaladaptive.models.UUIDField')(max_length=32)),
            ('debug_request', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('debug_response', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('purchaser', self.gf('django.db.models.fields.related.ForeignKey')(related_name='preapprovals_made', to=orm['auth.User'])),
            ('valid_until_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2011, 9, 19, 21, 4, 55, 279222))),
            ('preapproval_key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=10)),
            ('status_detail', self.gf('django.db.models.fields.CharField')(max_length=2048)),
        ))
        db.send_create_signal('paypaladaptive', ['Preapproval'])


    def backwards(self, orm):
        
        # Deleting model 'Payment'
        db.delete_table('paypaladaptive_payment')

        # Deleting model 'Refund'
        db.delete_table('paypaladaptive_refund')

        # Deleting model 'Preapproval'
        db.delete_table('paypaladaptive_preapproval')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'paypaladaptive.payment': {
            'Meta': {'object_name': 'Payment'},
            'amount': ('money.contrib.django.models.fields.MoneyField', [], {'default': 'None', 'max_digits': '6', 'decimal_places': '2', 'blank': 'True'}),
            'amount_currency': ('money.contrib.django.models.fields.CurrencyField', [], {'default': 'None', 'max_length': '3'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'debug_request': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'debug_response': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'payments_received'", 'null': 'True', 'to': "orm['auth.User']"}),
            'pay_key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'purchaser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'payments_made'", 'to': "orm['auth.User']"}),
            'secret_uuid': ('paypaladaptive.models.UUIDField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '10'}),
            'status_detail': ('django.db.models.fields.CharField', [], {'max_length': '2048'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'})
        },
        'paypaladaptive.preapproval': {
            'Meta': {'object_name': 'Preapproval'},
            'amount': ('money.contrib.django.models.fields.MoneyField', [], {'default': 'None', 'max_digits': '6', 'decimal_places': '2', 'blank': 'True'}),
            'amount_currency': ('money.contrib.django.models.fields.CurrencyField', [], {'default': 'None', 'max_length': '3'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'debug_request': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'debug_response': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'preapproval_key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'purchaser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'preapprovals_made'", 'to': "orm['auth.User']"}),
            'secret_uuid': ('paypaladaptive.models.UUIDField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '10'}),
            'status_detail': ('django.db.models.fields.CharField', [], {'max_length': '2048'}),
            'valid_until_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2011, 9, 19, 21, 4, 55, 287664)'})
        },
        'paypaladaptive.refund': {
            'Meta': {'object_name': 'Refund'},
            'amount': ('money.contrib.django.models.fields.MoneyField', [], {'default': 'None', 'max_digits': '6', 'decimal_places': '2', 'blank': 'True'}),
            'amount_currency': ('money.contrib.django.models.fields.CurrencyField', [], {'default': 'None', 'max_length': '3'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'debug_request': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'debug_response': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'payment': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['paypaladaptive.Payment']", 'unique': 'True'}),
            'secret_uuid': ('paypaladaptive.models.UUIDField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '10'}),
            'status_detail': ('django.db.models.fields.CharField', [], {'max_length': '2048'})
        }
    }

    complete_apps = ['paypaladaptive']
