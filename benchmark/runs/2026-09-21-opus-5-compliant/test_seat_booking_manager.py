# Standard library logging, silenced so the observability logs do not pollute the test output.
import logging
# Standard library test framework used by the whole suite.
import unittest
# Standard library mocking tool, used to isolate the class under test from every collaborator.
from unittest.mock import MagicMock

# Class under test and the generic exception it raises, imported from the single module of the package.
from seat_booking import ProcessingException, SeatBookingManager

# Silences every logger for the duration of this test module.
logging.disable(logging.CRITICAL)


# Mirror test class of SeatBookingManager.
class SeatBookingManagerTest(unittest.TestCase):

    # Covers the construction of the service layer over a supplied persistence layer.
    def test___init__(self):
        # Builds the service layer over a mocked persistence layer.
        result = SeatBookingManager(MagicMock())
        # Checks that the service layer was built.
        self.assertIsNotNone(result)

    # Covers the construction of the service layer over its own persistence layer.
    def test___init__2(self):
        # Builds the service layer without supplying a persistence layer.
        result = SeatBookingManager()
        # Checks that the service layer was built.
        self.assertIsNotNone(result)

    # Covers the registration of a room.
    def test_create_room(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Registers a room with a valid geometry.
        SeatBookingManager(data).create_room("room", 2, 3)
        # Checks that the service layer pushed the room row down to the persistence layer.
        data.save_room.assert_called_once()

    # Covers the rejection of a room with no row.
    def test_create_room2(self):
        # Builds the service layer over a mocked persistence layer.
        data = SeatBookingManager(MagicMock())
        # Checks that a room with no row is refused by the service layer.
        self.assertRaises(ProcessingException, data.create_room, "room", 0, 3)

    # Covers the rejection of a room with no seat per row.
    def test_create_room3(self):
        # Builds the service layer over a mocked persistence layer.
        data = SeatBookingManager(MagicMock())
        # Checks that a room with no seat per row is refused by the service layer.
        self.assertRaises(ProcessingException, data.create_room, "room", 2, 0)

    # Covers the registration of a screening.
    def test_create_screening(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Registers a screening in a room.
        SeatBookingManager(data).create_screening("screening", "room")
        # Checks that the service layer pushed the screening row down to the persistence layer.
        data.save_screening.assert_called_once()

    # Covers the rejection of a screening the persistence layer refuses.
    def test_create_screening2(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Makes the persistence layer refuse the insertion.
        data.save_screening.side_effect = ValueError("info")
        # Checks that the refusal crosses the service layer as the generic exception.
        self.assertRaises(ProcessingException, SeatBookingManager(data).create_screening, "screening", "room")

    # Covers the booking of a free seat.
    def test_book_seat(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Answers a free seat row when the position is read.
        data.load_seat.return_value.get_booked_flg.return_value = 0
        # Books the free seat for a client.
        SeatBookingManager(data).book_seat("screening", 1, 1, "client")
        # Checks that the service layer pushed the updated seat row down to the persistence layer.
        data.save_seat.assert_called_once()

    # Covers the rejection of a booking carrying no client.
    def test_book_seat2(self):
        # Builds the service layer over a mocked persistence layer.
        data = SeatBookingManager(MagicMock())
        # Checks that a booking without a client is refused by the service layer.
        self.assertRaises(ProcessingException, data.book_seat, "screening", 1, 1, None)

    # Covers the rejection of a booking on an already booked seat.
    def test_book_seat3(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Answers an already booked seat row when the position is read.
        data.load_seat.return_value.get_booked_flg.return_value = 1
        # Checks that the second booking of the same seat is refused by the service layer.
        self.assertRaises(ProcessingException, SeatBookingManager(data).book_seat, "screening", 1, 1, "client")

    # Covers the booking of an already booked seat when the caller allows a rebooking.
    def test_book_seat4(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Answers an already booked seat row when the position is read.
        data.load_seat.return_value.get_booked_flg.return_value = 1
        # Books the seat again with the rebooking flag raised.
        SeatBookingManager(data).book_seat("screening", 1, 1, "client", True)
        # Checks that the service layer pushed the updated seat row down to the persistence layer.
        data.save_seat.assert_called_once()

    # Covers the exposure of the availability of every seat of a screening.
    def test_get_seat_availability(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Mocks the free seat row attached to the loaded screening graph.
        info = MagicMock()
        # Answers a fixed row number.
        info.get_row_num.return_value = 1
        # Answers a fixed seat number.
        info.get_seat_num.return_value = 1
        # Answers a free seat.
        info.get_booked_flg.return_value = 0
        # Attaches the single seat row to the loaded screening graph.
        data.load_screening.return_value.get_seats.return_value = [info]
        # Builds the service layer over the mocked persistence layer.
        result = SeatBookingManager(data)
        # Mocks the utility shaping the answer, so no real collaborator runs.
        result.util = MagicMock()
        # Reads the availability of every seat of the screening.
        result.get_seat_availability("screening")
        # Checks that the service layer handed the records to the utility.
        result.util.sort_list.assert_called_once()

    # Covers the exposure of the free seats only.
    def test_get_seat_availability2(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Mocks the booked seat row attached to the loaded screening graph.
        info = MagicMock()
        # Answers a fixed row number.
        info.get_row_num.return_value = 1
        # Answers a fixed seat number.
        info.get_seat_num.return_value = 1
        # Answers an already booked seat.
        info.get_booked_flg.return_value = 1
        # Attaches the single seat row to the loaded screening graph.
        data.load_screening.return_value.get_seats.return_value = [info]
        # Builds the service layer over the mocked persistence layer.
        result = SeatBookingManager(data)
        # Mocks the utility shaping the answer, so no real collaborator runs.
        result.util = MagicMock()
        # Reads the availability of the free seats only, which drops the booked one.
        result.get_seat_availability("screening", True)
        # Checks that the service layer handed the records to the utility.
        result.util.sort_list.assert_called_once()

    # Covers the rejection of an availability read the persistence layer refuses.
    def test_get_seat_availability3(self):
        # Mocks the persistence layer used by the service layer.
        data = MagicMock()
        # Makes the persistence layer refuse the read.
        data.load_screening.side_effect = ValueError("info")
        # Checks that the refusal crosses the service layer as the generic exception.
        self.assertRaises(ProcessingException, SeatBookingManager(data).get_seat_availability, "screening")
