```
RECENCY STUDY — last-season-only model (A) vs last+current season, time-weighted (B)

=== carry>test 2425>2526
arm               rated%     n  brier1X2  logloss  brierOU  |gap|H  SPLIT%     BANKER n/hit/roi       SAFE n/hit/roi
A_static           65.8%  2999    0.6140   1.0248   0.2547   0.079    7.5%        98/87%/+11.0%       2673/71%/-7.9%
B_recent_hl120     94.4%  2999    0.6057   1.0128   0.2556   0.059    5.9%        103/82%/+4.4%       2715/72%/-6.4%
B_recent_hl240     94.4%  2999    0.6029   1.0086   0.2530   0.053    4.5%        104/83%/+5.7%       2757/72%/-6.7%

=== carry>test 2526>2627
arm               rated%     n  brier1X2  logloss  brierOU  |gap|H  SPLIT%     BANKER n/hit/roi       SAFE n/hit/roi
A_static           57.1%   497    0.6282   1.0436   0.2524   0.062    3.8%        8/100%/+26.1%        469/71%/-8.8%
B_recent_hl120     62.1%   497    0.6300   1.0469   0.2510   0.065    5.2%        5/100%/+24.2%        465/74%/-5.0%
B_recent_hl240     62.1%   497    0.6271   1.0426   0.2506   0.058    3.6%        6/100%/+24.5%        472/74%/-4.6%

```
