import csv
import urllib2
from datetime import datetime
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ...models import Division, DivisionGeometry, TemporalSet

OCDID_URL = 'https://raw.github.com/opencivicdata/ocd-division-ids/master/'

def load_divisions(clear=False):
    if clear:
        Division.objects.all().delete()

    url = OCDID_URL + 'identifiers/country-{}.csv'.format(settings.IMAGO_COUNTRY)

    count = 0
    for ocd_id, name in csv.reader(urllib2.urlopen(url)):
        pieces = ocd_id.split('/')
        if pieces.pop(0) != 'ocd-division':
            raise Exception('ID must start with ocd-division/')
        country = pieces.pop(0)
        if not country.startswith('country:'):
            raise Exception('Second part of ID must be country:')
        else:
            country = country.replace('country:', "")
        n = 1
        args = {}
        for piece in pieces:
            type_, id_ = piece.split(':')
            args['subtype%s' % n] = type_
            args['subid%s' % n] = id_
            n += 1

        d = Division(id=ocd_id, display_name=name.decode('latin1'), country=country, **args)
        d.save()

        count += 1
    print count, 'divisions'


def load_mapping(boundary_set_id, start, url, end=None):
    geoid_mapping = {}
    if not url.startswith('http'):
        url = OCDID_URL + 'mappings/' + url
    print(boundary_set_id, url)
    for ocd_id, geo_id in csv.reader(urllib2.urlopen(url)):
        geoid_mapping[geo_id] = ocd_id

    # delete temporal set & mappings if they exist
    tset = TemporalSet.objects.filter(boundary_set_id=boundary_set_id)
    if tset:
        print('Deleting existing TemporalSet')
        tset[0].geometries.all().delete()
        tset[0].delete()

    # create temporal set
    tset = TemporalSet.objects.create(boundary_set_id=boundary_set_id, start=start, end=end)
    for boundary in tset.boundary_set.boundaries.all():
        ocd_id = geoid_mapping.get(boundary.external_id)
        if ocd_id:
            DivisionGeometry.objects.create(division_id=ocd_id, temporal_set=tset,
                                            boundary=boundary)
        else:
            print 'unmatched external id', boundary, boundary.external_id


class Command(BaseCommand):
    help = 'Loads in division ids'

    option_list = BaseCommand.option_list + (
        make_option('--clear', action='store_true', dest='clear',
                    default=False, help='Clear divisions first.'),
    )

    def handle(self, *args, **options):
        load_divisions(options['clear'])
        for set_id, d in settings.IMAGO_BOUNDARY_MAPPINGS.items():
            load_mapping(set_id, **d)
