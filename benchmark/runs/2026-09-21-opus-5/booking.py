"""Seat booking for cinema screenings.

Everything this feature needs lives here: rooms, screenings, the bookings
themselves and the availability view. A reader can follow a booking from the
public method down to the stored state without opening another file.

State is held in memory. Swapping in persistence later means changing the three
dictionaries below and nothing else.
"""


class BookingError(Exception):
    """Base class for every error raised by this module."""


class UnknownRoomError(BookingError):
    """Raised when a screening refers to a room that was never registered."""


class UnknownScreeningError(BookingError):
    """Raised when a screening id is not scheduled."""


class NoSuchSeatError(BookingError):
    """Raised when a seat is outside the room's rows or seats per row."""


class SeatAlreadyBookedError(BookingError):
    """Raised when a seat is booked twice.

    Carries the client already holding the seat so a caller can tell the
    difference between "someone else took it" and "you already have it".
    """

    def __init__(self, screening_id, row, number, client_id):
        super().__init__(
            "seat %s-%s of screening %r is already booked by %r"
            % (row, number, screening_id, client_id)
        )
        self.screening_id = screening_id
        self.row = row
        self.number = number
        self.client_id = client_id


class SeatBookingManager:
    """Registers rooms, schedules screenings, books seats, reports availability.

    Rows and seats are numbered from 1, the way they are printed on a ticket.
    A seat is identified by the pair (row, number) within one screening; two
    screenings in the same room keep independent bookings.
    """

    def __init__(self):
        # room id -> (row count, seats per row)
        self._rooms = {}
        # screening id -> room id
        self._screenings = {}
        # screening id -> {(row, number): client id}
        self._bookings = {}

    def register_room(self, room_id, row_count, seats_per_row):
        """Declare a room shaped as `row_count` rows of `seats_per_row` seats."""
        if row_count < 1:
            raise ValueError("row_count must be at least 1, got %r" % (row_count,))
        if seats_per_row < 1:
            raise ValueError(
                "seats_per_row must be at least 1, got %r" % (seats_per_row,)
            )
        self._rooms[room_id] = (row_count, seats_per_row)

    def schedule_screening(self, screening_id, room_id):
        """Schedule a screening in an already registered room."""
        if room_id not in self._rooms:
            raise UnknownRoomError("unknown room %r" % (room_id,))
        self._screenings[screening_id] = room_id
        # A fresh screening starts with every seat free.
        self._bookings[screening_id] = {}

    def book_seat(self, screening_id, row, number, client_id):
        """Book one seat for one client, or reject the request.

        Rejection cases, each with its own exception: unknown screening, seat
        outside the room, seat already taken.
        """
        room_id = self._screenings.get(screening_id)
        if room_id is None:
            raise UnknownScreeningError("unknown screening %r" % (screening_id,))
        row_count, seats_per_row = self._rooms[room_id]
        if not 1 <= row <= row_count or not 1 <= number <= seats_per_row:
            raise NoSuchSeatError(
                "seat %s-%s is outside room %r (%s rows of %s seats)"
                % (row, number, room_id, row_count, seats_per_row)
            )
        booked = self._bookings[screening_id]
        holder = booked.get((row, number))
        # A booked seat is never reassigned, not even to the client holding it.
        if holder is not None:
            raise SeatAlreadyBookedError(screening_id, row, number, holder)
        booked[(row, number)] = client_id
        return {
            "screening_id": screening_id,
            "row": row,
            "number": number,
            "client_id": client_id,
        }

    def availability(self, screening_id):
        """Return every seat of the screening, row by row, seat by seat.

        Each entry carries the seat coordinates, whether it is still available
        and the client holding it (None when free).
        """
        room_id = self._screenings.get(screening_id)
        if room_id is None:
            raise UnknownScreeningError("unknown screening %r" % (screening_id,))
        row_count, seats_per_row = self._rooms[room_id]
        booked = self._bookings[screening_id]
        seats = []
        for row in range(1, row_count + 1):
            for number in range(1, seats_per_row + 1):
                holder = booked.get((row, number))
                seats.append(
                    {
                        "row": row,
                        "number": number,
                        "available": holder is None,
                        "client_id": holder,
                    }
                )
        return seats
