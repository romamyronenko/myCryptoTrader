"""Trading signals.

Signals are pure functions of OHLCV. They never import an exchange client, so
they can be unit-tested and reused by both the backtester and Freqtrade.
"""
