from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session
from app.entities import Client, Tarif

B = '/api/v1'
PHONE = '+79001234567'


@pytest.fixture
def data(api):
    with Session(api.test_engine) as s:
        cheap = Tarif(tarif_name='Эконом', internet=10, count_minutes=100, count_sms=10, salary=Decimal('300'))
        costly = Tarif(tarif_name='Безлимит', internet=50, count_minutes=500, count_sms=100, salary=Decimal('600'))
        empty = Tarif(tarif_name='Без клиентов', internet=0, count_minutes=0, count_sms=0, salary=Decimal('0'))
        s.add_all([cheap, costly, empty]); s.commit()
        ids = [cheap.id_tarif, costly.id_tarif, empty.id_tarif]
        for phone, tariff, birthday, issue in [(PHONE, ids[0], '1995-10-20', '2015-12-31'), ('88001234567', ids[1], '1990-05-15', '2016-01-01')]:
            s.add(Client(number_phone=phone, id_tarif=tariff, lastname='Иванов', firstname='Иван', patronymic_name='Иванович', date_birthday=date.fromisoformat(birthday), date_issue=date.fromisoformat(issue), pasport_serial='0012', pasport_number='000123'))
        s.commit()
    return ids


def test_exact_contract(api):
    spec = api.get(B+'/openapi.json').json()
    actual = {(method.upper(),path.removeprefix(B)) for path, methods in spec['paths'].items() for method in methods}
    assert actual == {
        ('GET','/tarifs'), ('POST','/tarifs'), ('GET','/tarifs/by-client/{phone}'),
        ('GET','/tarifs/stats/client-count'), ('GET','/tarifs/{id}/client-count'),
        ('PUT','/tarifs/{id}'), ('DELETE','/tarifs/{id_tarif}'), ('GET','/tarifs/with-client-count'),
        ('GET','/clients/search/phone'), ('GET','/clients/sorted-by-birthday'),
        ('GET','/clients/search/passport-year'), ('GET','/clients/search/tarif-cost'),
        ('GET','/clients/with-tarif'), ('PUT','/clients/{phone}'), ('DELETE','/clients/{phone}'), ('PATCH','/clients/tarif'),
    }
    assert api.get(B+'/docs').status_code == 200
    from sqlmodel import SQLModel
    assert set(SQLModel.metadata.tables) == {'client','tarif'}
    example = spec['components']['schemas']['ClientUpdate']['example']
    assert example == {'lastname': 'Петров'}


def test_tarif_queries(api, data):
    assert len(api.get(B+'/tarifs').json()) == 3
    assert api.get(B+f'/tarifs/by-client/{PHONE}').json()['id_tarif'] == data[0]
    assert api.get(B+'/tarifs/stats/client-count').json() == [
        {'tarif_name':'Эконом','client_count':1}, {'tarif_name':'Безлимит','client_count':1}, {'tarif_name':'Без клиентов','client_count':0}]
    assert api.get(B+f'/tarifs/{data[0]}/client-count').json() == {'tarif_id':data[0],'count':1}
    rows = api.get(B+'/tarifs/with-client-count').json()
    assert [r['client_count'] for r in rows] == [1,1,0]
    assert rows[0]['salary'] == 300


def test_client_queries_do_not_mutate(api, data):
    before = api.get(B+'/clients/with-tarif').json()
    for _ in range(2):
        rows=api.get(B+'/clients/search/phone',params={'phone':'+7'}).json()
        assert rows == [{'number_phone':PHONE,'lastname':'Иванов','firstname':'Иван'}]
        assert len(api.get(B+'/clients/search/phone',params={'phone':'8'}).json()) == 1
        assert api.get(B+'/clients/search/phone',params={'phone':'+44'}).json() == []
        rows=api.get(B+'/clients/sorted-by-birthday').json()
        assert [r['date_birthday'] for r in rows] == ['1990-05-15','1995-10-20']
        assert rows[0]['full_name'] == 'Иванов Иван Иванович'
        rows=api.get(B+'/clients/search/passport-year',params={'year':2015}).json()
        assert [r['number_phone'] for r in rows] == ['88001234567']
        assert api.get(B+'/clients/search/passport-year',params={'year':2016}).json() == []
        rows=api.get(B+'/clients/search/tarif-cost',params={'minSalary':300}).json()
        assert len(rows)==1 and rows[0]['tarif']['salary']==600
        assert api.get(B+'/clients/search/tarif-cost',params={'minSalary':600}).json()==[]
    assert api.get(B+'/clients/with-tarif').json() == before


def test_client_changes(api, data):
    r=api.put(B+f'/clients/{PHONE}',json={'lastname':'Петров'})
    assert r.status_code==200 and r.json()['number_phone']==PHONE and r.json()['firstname']=='Иван'
    assert api.put(B+f'/clients/{PHONE}',json={'number_phone':'+79999999999'}).status_code==422
    r=api.patch(B+'/clients/tarif',params={'phone':PHONE,'id_tarif':data[1]})
    assert r.status_code==200 and r.json()['message']
    assert api.get(B+f'/tarifs/{data[1]}/client-count').json()['count']==2
    assert api.delete(B+f'/tarifs/{data[1]}').status_code==409
    r=api.delete(B+f'/clients/{PHONE}')
    assert r.status_code==204 and r.content==b''
    assert api.get(B+'/clients/search/phone',params={'phone':'+7'}).json()==[]


def test_tarif_changes(api):
    r=api.post(B+'/tarifs',json={'tarif_name':'Новый тариф','internet':50,'count_minutes':500,'count_sms':100,'salary':600})
    assert r.status_code==201
    t=r.json()
    r=api.put(B+f"/tarifs/{t['id_tarif']}",json={'salary':'600.25'})
    assert r.status_code==200 and r.json()=={**t,'salary':600.25}
    r=api.delete(B+f"/tarifs/{t['id_tarif']}")
    assert r.status_code==204 and not r.content


@pytest.mark.parametrize('method,path,kwargs',[
    ('get','/tarifs/9999/client-count',{}), ('get','/tarifs/by-client/+79999999999',{}),
    ('put','/tarifs/9999',{'json':{'salary':100}}), ('delete','/tarifs/9999',{}),
    ('put','/clients/+79999999999',{'json':{'lastname':'Петров'}}), ('delete','/clients/+79999999999',{}),
    ('patch','/clients/tarif',{'params':{'phone':'+79999999999','id_tarif':1}}),
])
def test_missing(api,method,path,kwargs):
    assert api.request(method,B+path,**kwargs).status_code==404


@pytest.mark.parametrize('path,params',[
    ('/clients/search/phone',{}), ('/clients/search/phone',{'phone':'%'}),
    ('/clients/search/passport-year',{'year':10000}), ('/clients/search/tarif-cost',{'minSalary':-1}),
])
def test_invalid_queries(api,path,params):
    assert api.get(B+path,params=params).status_code==422


def test_failed_updates_preserve_records(api,data):
    before=api.get(B+'/clients/with-tarif').json()
    for body,status in [({'firstname':None},422),({'date_issue':'invalid'},422),({'id_tarif':9999},404)]:
        assert api.put(B+f'/clients/{PHONE}',json=body).status_code==status
    assert api.get(B+'/clients/with-tarif').json()==before
    for body in [{'salary':-1},{'salary':None},{'salary':'0.001'},{'tarif_name':' '}]:
        assert api.put(B+f'/tarifs/{data[0]}',json=body).status_code==422
