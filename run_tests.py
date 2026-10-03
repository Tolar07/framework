import sys
sys.path.insert(0, 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv')

# Run multi_source_test
exec(open('tests/multi_source_test.py').read())
print("multi_source_test: PASSED")

# Run api_football_plan_test
exec(open('tests/api_football_plan_test.py').read())
print("api_football_plan_test: PASSED")

# Run clubelo_source_test
exec(open('tests/clubelo_source_test.py').read())
print("clubelo_source_test: PASSED")

# Run clubelo_fallback_test
exec(open('tests/clubelo_fallback_test.py').read())
print("clubelo_fallback_test: PASSED")

print("\nALL TESTS PASSED")