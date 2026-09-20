"""Decorator shims used only by the desktop simulator/tests."""
class micropython:
    @staticmethod
    def native(fn): return fn
    @staticmethod
    def viper(fn): return fn
