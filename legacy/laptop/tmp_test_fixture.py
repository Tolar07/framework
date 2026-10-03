import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')

from pipeline.fixture_extraction import VerifiedFixture, StageAOutput

vf = VerifiedFixture(
    league='Premier League',
    home_team='Arsenal',
    away_team='Chelsea',
    kickoff_utc='2026-08-25T19:45:00Z',
    kickoff_date='2026-08-25',
    verification_tier='VERIFIED',
    verification_note='OK',
    verification_factors={},
    source='thesportsdb.com',
    source_tier='T2',
    status='verified',
)
d = vf.to_dict()
vf2 = VerifiedFixture.from_dict(d)

output = StageAOutput(
    run_date='2026-08-20',
    fixtures_season='2627',
    leagues_scanned=['Premier League'],
    fixtures=[vf2],
    flags=['test'],
    stats={'total_fixtures': 1}
)
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / 'test.json'
    output.save(path)
    loaded = StageAOutput.load(path)
    print('run_date:', loaded.run_date)
    print('fixtures_season:', loaded.fixtures_season)
    print('fixtures count:', len(loaded.fixtures))
    print('home_team:', loaded.fixtures[0].home_team)

print('OK')
