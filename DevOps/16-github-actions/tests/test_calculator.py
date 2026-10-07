import pytest

from app.calculator import add, divide, multiply, subtract


def test_add():
    assert add(10, 5) == 15


def test_add_negative():
    assert add(-2, -3) == -5


def test_subtract():
    assert subtract(10, 5) == 5


def test_multiply():
    assert multiply(10, 5) == 50


def test_divide():
    assert divide(10, 5) == 2


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)
