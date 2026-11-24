# Mirror test for BookingManager: one test per method (numbered when a method has several branches).
# Collaborators (gateway, clock, screening, room) are mocks.
import unittest
from datetime import datetime, timedelta
from unittest import mock
from seat_booking import (BookingManager, ProcessingException, TransientGatewayError,
                          PermanentGatewayError, GatewayUnavailableError)

NOW = datetime(2026, 1, 1, 12, 0)


def make_manager(gateway=None):
    return BookingManager(gateway or mock.Mock(), clock=lambda: NOW)


def make_screening(hours_ahead=5, valid_seat=True):
    screening = mock.Mock()
    screening.screening_id = 1
    screening.price = 10
    screening.start_time = NOW + timedelta(hours=hours_ahead)
    screening.room.has_seat.return_value = valid_seat
    return screening


class BookingManagerTest(unittest.TestCase):
    def test_init(self):
        self.assertEqual(make_manager().bookings, {})

    def test_reject(self):
        with self.assertRaises(ProcessingException):
            make_manager().reject("m", "r")

    def test_book(self):
        self.assertEqual(make_manager().book("c", make_screening(), 1, 1).booking_id, 1)

    def test_book2(self):
        with self.assertRaises(ProcessingException):
            make_manager().book("c", make_screening(valid_seat=False), 1, 1)

    def test_book3(self):
        with self.assertRaises(ProcessingException):
            make_manager().book("c", make_screening(hours_ahead=-1), 1, 1)

    def test_book4(self):
        manager, screening = make_manager(), make_screening()
        manager.book("c", screening, 1, 1)
        with self.assertRaises(ProcessingException):
            manager.book("d", screening, 1, 1)

    def test_book5(self):
        manager, screening = make_manager(), make_screening()
        manager.book("c", screening, 1, 1)
        self.assertEqual(manager.book("d", screening, 1, 2).booking_id, 2)

    def test_book6(self):
        manager, screening = make_manager(), make_screening()
        manager.cancel(manager.book("c", screening, 1, 1).booking_id)
        self.assertEqual(manager.book("d", screening, 1, 1).booking_id, 2)

    def test_cancel(self):
        gateway = mock.Mock()
        manager = make_manager(gateway)
        manager.cancel(manager.book("c", make_screening(), 1, 1).booking_id)
        gateway.refund.assert_called_once_with(1, 10)

    def test_cancel2(self):
        with self.assertRaises(ProcessingException):
            make_manager().cancel(99)

    def test_cancel3(self):
        manager = make_manager()
        booking = manager.book("c", make_screening(), 1, 1)
        manager.cancel(booking.booking_id)
        with self.assertRaises(ProcessingException):
            manager.cancel(booking.booking_id)

    def test_cancel4(self):
        manager = make_manager()
        booking = manager.book("c", make_screening(hours_ahead=1), 1, 1)
        with self.assertRaises(ProcessingException):
            manager.cancel(booking.booking_id)

    def test_cancel5(self):
        gateway = mock.Mock()
        gateway.refund.side_effect = [TransientGatewayError(), TransientGatewayError(), None]
        manager = make_manager(gateway)
        manager.cancel(manager.book("c", make_screening(), 1, 1).booking_id)
        self.assertEqual(gateway.refund.call_count, 3)

    def test_cancel6(self):
        gateway = mock.Mock()
        gateway.refund.side_effect = TransientGatewayError()
        manager = make_manager(gateway)
        with self.assertRaises(ProcessingException):
            manager.cancel(manager.book("c", make_screening(), 1, 1).booking_id)

    def test_cancel7(self):
        gateway = mock.Mock()
        gateway.refund.side_effect = PermanentGatewayError()
        manager = make_manager(gateway)
        with self.assertRaises(ProcessingException):
            manager.cancel(manager.book("c", make_screening(), 1, 1).booking_id)

    def test_cancel8(self):
        gateway = mock.Mock()
        gateway.refund.side_effect = GatewayUnavailableError()
        manager = make_manager(gateway)
        with self.assertRaises(ProcessingException):
            manager.cancel(manager.book("c", make_screening(), 1, 1).booking_id)

    def test_get_refund_status(self):
        manager = make_manager()
        self.assertEqual(manager.get_refund_status(manager.book("c", make_screening(), 1, 1).booking_id), "NONE")

    def test_get_refund_status2(self):
        with self.assertRaises(ProcessingException):
            make_manager().get_refund_status(99)
