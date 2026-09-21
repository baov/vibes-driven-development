"""Seat reservation service for a cinema chain.

Domain vocabulary: a Room has rows and seats. A Screening happens in a Room
and carries its own independent seat availability, so the same room can
host several screenings without one's bookings affecting another. A client
books a Seat for a Screening; booking a seat that is already booked is
rejected with SeatAlreadyBookedError.
"""

# standard library only: used to log every exception at this module's
# boundary, per this codebase's "Observability first" convention
import logging

# module-level logger used to record every exception this module raises
logger = logging.getLogger(__name__)


# Generic exception used at this module's boundary: unexpected lower-level
# failures are wrapped into this type so callers never depend on
# implementation details (per AGENTS.md, "Observability first").
class ProcessingException(Exception):
    # no extra behavior: the class exists purely to hide the original cause
    pass


# Raised when a client tries to book a seat that is already held by someone.
class SeatAlreadyBookedError(Exception):
    # no extra behavior: the type itself carries the meaning
    pass


# Raised when a screening id passed to the manager does not exist.
class ScreeningNotFoundError(Exception):
    # no extra behavior: the type itself carries the meaning
    pass


# Raised when a (row, seat number) pair does not exist in a screening's room.
class SeatNotFoundError(Exception):
    # no extra behavior: the type itself carries the meaning
    pass


# A single seat inside a screening. Plain data holder, per this codebase's
# domain-design convention: entities are fields with getters/setters.
class Seat:
    def __init__(self, row, number):
        # the row this seat sits in, 1-indexed
        self.row = row
        # the seat number within its row, 1-indexed
        self.number = number
        # the id of the client currently holding this seat, None if free
        self.booked_by = None

    # returns whether the seat currently has no holder
    def is_available(self):
        # a seat is free exactly when nobody has booked it
        return self.booked_by is None


# A physical room: a fixed number of rows and seats per row. Plain data
# holder shared by every screening scheduled in that room.
class Room:
    def __init__(self, name, rows, seats_per_row):
        # human-readable identifier for the room
        self.name = name
        # total number of rows in the room
        self.rows = rows
        # total number of seats in each row
        self.seats_per_row = seats_per_row


# A screening of a movie in a room, at a given time slot. Owns its own seat
# map so the same room can host several screenings with independent
# availability.
class Screening:
    def __init__(self, screening_id, room):
        # unique identifier for this screening
        self.screening_id = screening_id
        # the room this screening takes place in
        self.room = room
        # build a fresh, all-available seat map from the room's layout
        self.seats = {}
        # walk every row of the room, rows are 1-indexed
        for row in range(1, room.rows + 1):
            # walk every seat position within that row, also 1-indexed
            for number in range(1, room.seats_per_row + 1):
                # create a fresh, unbooked seat for this (row, number) slot
                self.seats[(row, number)] = Seat(row, number)

    # returns the Seat at (row, number), or None if it does not exist
    def get_seat(self, row, number):
        # look up the seat by its (row, number) key, defaulting to None
        return self.seats.get((row, number))


# Handles booking operations and availability queries across screenings.
# Behavior lives here rather than on the entities, per this codebase's
# convention that business logic belongs in *Manager/*Service classes.
class BookingManager:
    def __init__(self):
        # registry of every screening this manager knows about, by id
        self.screenings = {}

    # registers a screening so it can later accept bookings
    def add_screening(self, screening):
        # store the screening under its own id for later lookup
        self.screenings[screening.screening_id] = screening

    # books a seat for a client; rejects the booking if already taken
    def book_seat(self, screening_id, row, number, client_id):
        # everything below is one layer boundary: unexpected failures get
        # logged and wrapped before leaving this method
        try:
            # look up the screening the client wants to book into
            screening = self.screenings.get(screening_id)
            # a missing screening is a usage error the caller must fix
            if screening is None:
                raise ScreeningNotFoundError(screening_id)
            # look up the requested seat within that screening
            seat = screening.get_seat(row, number)
            # a missing seat is a usage error the caller must fix
            if seat is None:
                raise SeatNotFoundError((row, number))
            # reject the booking outright if the seat is already held
            if not seat.is_available():
                raise SeatAlreadyBookedError((screening_id, row, number))
            # record the client as the new holder of the seat
            seat.booked_by = client_id
        except (ScreeningNotFoundError, SeatNotFoundError, SeatAlreadyBookedError) as exc:
            # log the expected domain exception at this layer
            logger.exception("book_seat failed: %s", exc)
            # rethrow the same domain exception so callers can react to it
            raise
        except Exception:
            # log any unexpected lower-level failure at this layer
            logger.exception("book_seat failed unexpectedly")
            # wrap it in the generic boundary exception; the original cause
            # is omitted, per this codebase's observability convention
            raise ProcessingException("booking failed") from None

    # returns the availability of every seat of a screening
    def get_availability(self, screening_id):
        # everything below is one layer boundary: unexpected failures get
        # logged and wrapped before leaving this method
        try:
            # look up the screening whose availability is being queried
            screening = self.screenings.get(screening_id)
            # a missing screening is a usage error the caller must fix
            if screening is None:
                raise ScreeningNotFoundError(screening_id)
            # accumulate one availability entry per seat, in a stable order
            result = []
            # walk every (row, number) key in a stable, sorted order
            for row, number in sorted(screening.seats.keys()):
                # fetch the seat itself for this (row, number) key
                seat = screening.seats[(row, number)]
                # append its availability as a plain dict entry
                result.append(
                    {
                        "row": row,
                        "number": number,
                        "available": seat.is_available(),
                    }
                )
            # hand back the full availability list to the caller
            return result
        except ScreeningNotFoundError as exc:
            # log the expected domain exception at this layer
            logger.exception("get_availability failed: %s", exc)
            # rethrow the same domain exception so callers can react to it
            raise
        except Exception:
            # log any unexpected lower-level failure at this layer
            logger.exception("get_availability failed unexpectedly")
            # wrap it in the generic boundary exception; the original cause
            # is omitted, per this codebase's observability convention
            raise ProcessingException("availability lookup failed") from None
