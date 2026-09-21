# Standard library logging, required so that no layer stays blind to a failure.
import logging

# Module level logger shared by every layer of this module.
LOGGER = logging.getLogger("seat_booking")


# Generic exception raised at every layer boundary so that implementation details never leak out.
class ProcessingException(Exception):
    # No extra field is added: the message carries everything a caller is allowed to know.
    pass


# Plain data structure describing a room, named after the room table it maps to.
class RoomEntity:

    # Builds a room from its identifier, its number of rows and its number of seats per row.
    def __init__(self, data=None, info=0, result=0):
        # Holds the room identifier column.
        self.room_id = data
        # Holds the row count column.
        self.row_cnt = info
        # Holds the seat count per row column.
        self.seat_cnt = result

    # Returns the room identifier column.
    def get_room_id(self):
        # Gives back the stored room identifier.
        return self.room_id

    # Overwrites the room identifier column.
    def set_room_id(self, data):
        # Stores the new room identifier.
        self.room_id = data

    # Returns the row count column.
    def get_row_cnt(self):
        # Gives back the stored row count.
        return self.row_cnt

    # Overwrites the row count column.
    def set_row_cnt(self, data):
        # Stores the new row count.
        self.row_cnt = data

    # Returns the seat count per row column.
    def get_seat_cnt(self):
        # Gives back the stored seat count per row.
        return self.seat_cnt

    # Overwrites the seat count per row column.
    def set_seat_cnt(self, data):
        # Stores the new seat count per row.
        self.seat_cnt = data


# Plain data structure describing a screening, named after the screening table it maps to.
class ScreeningEntity:

    # Builds a screening from its identifier and the identifier of the room hosting it.
    def __init__(self, data=None, info=None):
        # Holds the screening identifier column.
        self.screening_id = data
        # Holds the room identifier foreign key column.
        self.room_id = info
        # Holds the full room object graph, always loaded with the screening.
        self.room = None
        # Holds the full seat object graph, always loaded with the screening.
        self.seats = []

    # Returns the screening identifier column.
    def get_screening_id(self):
        # Gives back the stored screening identifier.
        return self.screening_id

    # Overwrites the screening identifier column.
    def set_screening_id(self, data):
        # Stores the new screening identifier.
        self.screening_id = data

    # Returns the room identifier foreign key column.
    def get_room_id(self):
        # Gives back the stored room identifier.
        return self.room_id

    # Overwrites the room identifier foreign key column.
    def set_room_id(self, data):
        # Stores the new room identifier.
        self.room_id = data

    # Returns the full room object graph attached to this screening.
    def get_room(self):
        # Gives back the stored room graph.
        return self.room

    # Overwrites the full room object graph attached to this screening.
    def set_room(self, data):
        # Stores the new room graph.
        self.room = data

    # Returns the full seat object graph attached to this screening.
    def get_seats(self):
        # Gives back the stored seat graph.
        return self.seats

    # Overwrites the full seat object graph attached to this screening.
    def set_seats(self, data):
        # Stores the new seat graph.
        self.seats = data


# Plain data structure describing one seat of one screening, named after the seat table it maps to.
class SeatEntity:

    # Builds a seat from its screening, its row number and its seat number.
    def __init__(self, data=None, info=0, result=0):
        # Holds the screening identifier foreign key column.
        self.screening_id = data
        # Holds the row number column.
        self.row_num = info
        # Holds the seat number column.
        self.seat_num = result
        # Holds the booked flag column, zero meaning the seat is still free.
        self.booked_flg = 0
        # Holds the client identifier column of the client owning the booking.
        self.client_id = None

    # Returns the screening identifier foreign key column.
    def get_screening_id(self):
        # Gives back the stored screening identifier.
        return self.screening_id

    # Overwrites the screening identifier foreign key column.
    def set_screening_id(self, data):
        # Stores the new screening identifier.
        self.screening_id = data

    # Returns the row number column.
    def get_row_num(self):
        # Gives back the stored row number.
        return self.row_num

    # Overwrites the row number column.
    def set_row_num(self, data):
        # Stores the new row number.
        self.row_num = data

    # Returns the seat number column.
    def get_seat_num(self):
        # Gives back the stored seat number.
        return self.seat_num

    # Overwrites the seat number column.
    def set_seat_num(self, data):
        # Stores the new seat number.
        self.seat_num = data

    # Returns the booked flag column.
    def get_booked_flg(self):
        # Gives back the stored booked flag.
        return self.booked_flg

    # Overwrites the booked flag column.
    def set_booked_flg(self, data):
        # Stores the new booked flag.
        self.booked_flg = data

    # Returns the client identifier column.
    def get_client_id(self):
        # Gives back the stored client identifier.
        return self.client_id

    # Overwrites the client identifier column.
    def set_client_id(self, data):
        # Stores the new client identifier.
        self.client_id = data


# Persistence layer keeping every row of every table in memory.
class SeatBookingStoreHelper:

    # Prepares the three in-memory tables handled by this helper.
    def __init__(self):
        # Holds the room table, keyed by room identifier.
        self.data = {}
        # Holds the screening table, keyed by screening identifier.
        self.info = {}
        # Holds the seat table, keyed by screening identifier then by row and seat number.
        self.result = {}

    # Inserts a room row into the room table.
    def save_room(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a room whose identifier is already present, since identifiers are unique.
            if data.get_room_id() in self.data:
                # Signals the duplicate to the caller of this layer.
                raise ValueError("room " + str(data.get_room_id()) + " already exists")
            # Stores the room row under its identifier.
            self.data[data.get_room_id()] = data
            # Hands the stored row back so the caller does not have to read it again.
            return data
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("save_room failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("save_room failed: " + str(tmp2)) from None

    # Reads a room row from the room table.
    def load_room(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects an unknown room identifier, since the caller expects a row.
            if data not in self.data:
                # Signals the missing row to the caller of this layer.
                raise ValueError("room " + str(data) + " is unknown")
            # Hands the stored room row back to the caller.
            return self.data[data]
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("load_room failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("load_room failed: " + str(tmp2)) from None

    # Inserts a screening row and the whole seat grid that belongs to it.
    def save_screening(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a screening whose identifier is already present, since identifiers are unique.
            if data.get_screening_id() in self.info:
                # Signals the duplicate to the caller of this layer.
                raise ValueError("screening " + str(data.get_screening_id()) + " already exists")
            # Rejects a screening pointing at a room that was never saved.
            if data.get_room_id() not in self.data:
                # Signals the dangling foreign key to the caller of this layer.
                raise ValueError("room " + str(data.get_room_id()) + " is unknown")
            # Stores the screening row under its identifier.
            self.info[data.get_screening_id()] = data
            # Opens an empty seat table for this screening.
            self.result[data.get_screening_id()] = {}
            # Reads the room row so the seat grid matches the geometry of the room.
            tmp2 = self.data[data.get_room_id()]
            # Walks every row of the room, rows being numbered from one.
            for info in range(1, tmp2.get_row_cnt() + 1):
                # Walks every seat of the current row, seats being numbered from one.
                for result in range(1, tmp2.get_seat_cnt() + 1):
                    # Builds the free seat row for this position.
                    self.result[data.get_screening_id()][(info, result)] = SeatEntity(
                        data.get_screening_id(), info, result
                    )
            # Hands the stored screening row back to the caller.
            return data
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("save_screening failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("save_screening failed: " + str(tmp2)) from None

    # Reads a screening row together with its full object graph.
    def load_screening(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects an unknown screening identifier, since the caller expects a row.
            if data not in self.info:
                # Signals the missing row to the caller of this layer.
                raise ValueError("screening " + str(data) + " is unknown")
            # Reads the screening row itself.
            info = self.info[data]
            # Attaches the full room graph, because a partial graph leaves the caller guessing.
            info.set_room(self.data[info.get_room_id()])
            # Prepares the seat list of the full graph.
            result = []
            # Walks every seat row stored for this screening.
            for tmp2 in self.result[data]:
                # Appends the seat row to the seat list of the graph.
                result.append(self.result[data][tmp2])
            # Attaches the full seat graph to the screening row.
            info.set_seats(result)
            # Hands the fully loaded screening row back to the caller.
            return info
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("load_screening failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("load_screening failed: " + str(tmp2)) from None

    # Reads one seat row of one screening.
    def load_seat(self, data, info, result):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects an unknown screening identifier, since the seat table is keyed by screening.
            if data not in self.result:
                # Signals the missing screening to the caller of this layer.
                raise ValueError("screening " + str(data) + " is unknown")
            # Rejects a position that lies outside the geometry of the room.
            if (info, result) not in self.result[data]:
                # Signals the missing seat to the caller of this layer.
                raise ValueError("seat " + str(info) + "-" + str(result) + " is unknown")
            # Hands the stored seat row back to the caller.
            return self.result[data][(info, result)]
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("load_seat failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("load_seat failed: " + str(tmp2)) from None

    # Updates one seat row of one screening.
    def save_seat(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a seat whose screening was never opened.
            if data.get_screening_id() not in self.result:
                # Signals the missing screening to the caller of this layer.
                raise ValueError("screening " + str(data.get_screening_id()) + " is unknown")
            # Stores the seat row at its position.
            self.result[data.get_screening_id()][(data.get_row_num(), data.get_seat_num())] = data
            # Hands the stored seat row back to the caller.
            return data
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("save_seat failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("save_seat failed: " + str(tmp2)) from None


# Utility exposing its own local collection and string helpers, so the module stays self-contained.
class SeatAvailabilityUtil:

    # Sorts a list of availability records by row then by seat, with a local helper.
    def sort_list(self, data):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Copies the incoming list so the caller keeps its own ordering.
            result = list(data)
            # Walks the copy once per element, which is enough for an insertion sort.
            for info in range(1, len(result)):
                # Remembers the element currently being inserted.
                tmp2 = result[info]
                # Walks backwards from the insertion point.
                while info > 0 and (
                    result[info - 1]["row"] > tmp2["row"]
                    or (result[info - 1]["row"] == tmp2["row"] and result[info - 1]["seat"] > tmp2["seat"])
                ):
                    # Shifts the bigger element one position to the right.
                    result[info] = result[info - 1]
                    # Moves the insertion point one position to the left.
                    info = info - 1
                # Drops the remembered element at its final position.
                result[info] = tmp2
            # Hands the sorted copy back to the caller.
            return result
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("sort_list failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("sort_list failed: " + str(tmp2)) from None

    # Builds the printable label of a seat, with a local string helper.
    def join_str(self, data, info):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Concatenates the row number and the seat number around a dash.
            return str(data) + "-" + str(info)
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("join_str failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("join_str failed: " + str(tmp2)) from None


# Service layer carrying every business rule about rooms, screenings and seat bookings.
class SeatBookingManager:

    # Builds the manager over a persistence helper, creating one when the caller gives none.
    def __init__(self, data=None):
        # Holds the persistence layer used by every operation of this manager.
        self.helper = data if data is not None else SeatBookingStoreHelper()
        # Holds the utility used to shape the availability answer.
        self.util = SeatAvailabilityUtil()

    # Registers a room of the given geometry.
    def create_room(self, data, info, result):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a room with no row, since such a room can host no screening.
            if info < 1:
                # Signals the invalid geometry to the caller of this layer.
                raise ValueError("a room needs at least one row")
            # Rejects a room with no seat per row, for the same reason.
            if result < 1:
                # Signals the invalid geometry to the caller of this layer.
                raise ValueError("a room needs at least one seat per row")
            # Builds the room row with the requested geometry.
            tmp2 = RoomEntity(data, info, result)
            # Pushes the room row down to the persistence layer.
            return self.helper.save_room(tmp2)
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("create_room failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("create_room failed: " + str(tmp2)) from None

    # Registers a screening taking place in an already known room.
    def create_screening(self, data, info):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Builds the screening row pointing at its room.
            tmp2 = ScreeningEntity(data, info)
            # Pushes the screening row down to the persistence layer, which opens the seat grid.
            return self.helper.save_screening(tmp2)
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("create_screening failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("create_screening failed: " + str(tmp2)) from None

    # Books one seat of one screening for one client, the last flag reopening an already booked seat.
    def book_seat(self, data, info, result, tmp2, allow_rebooking=False):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a booking with no client, since a booking always belongs to somebody.
            if tmp2 is None:
                # Signals the missing client to the caller of this layer.
                raise ValueError("a booking needs a client")
            # Reads the seat row at the requested position, which also validates the position.
            tmp3 = self.helper.load_seat(data, info, result)
            # Refuses the booking when the seat is already taken and the caller did not allow a rebooking.
            if tmp3.get_booked_flg() == 1 and allow_rebooking is False:
                # Signals the conflict to the caller of this layer.
                raise ValueError(
                    "seat " + str(info) + "-" + str(result) + " of screening " + str(data) + " is already booked"
                )
            # Raises the booked flag of the seat row.
            tmp3.set_booked_flg(1)
            # Writes the owner of the booking on the seat row.
            tmp3.set_client_id(tmp2)
            # Pushes the updated seat row down to the persistence layer.
            return self.helper.save_seat(tmp3)
        # Catches every failure crossing this layer boundary.
        except Exception as tmp4:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("book_seat failed: %s", tmp4)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("book_seat failed: " + str(tmp4)) from None

    # Exposes the availability of every seat of a screening, the flag dropping the booked ones.
    def get_seat_availability(self, data, only_available=False):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Reads the screening together with its full object graph.
            info = self.helper.load_screening(data)
            # Prepares the list of availability records handed back to the caller.
            result = []
            # Walks every seat of the loaded graph.
            for tmp2 in info.get_seats():
                # Skips the booked seats when the caller asked for the free ones only.
                if only_available is True and tmp2.get_booked_flg() == 1:
                    # Leaves this seat out of the answer.
                    continue
                # Appends the availability record of this seat, rebuilding the label locally.
                result.append(
                    {
                        "row": tmp2.get_row_num(),
                        "seat": tmp2.get_seat_num(),
                        "label": str(tmp2.get_row_num()) + "-" + str(tmp2.get_seat_num()),
                        "available": tmp2.get_booked_flg() == 0,
                        "client_id": tmp2.get_client_id(),
                    }
                )
            # Hands the records back in a stable order so the caller can display them directly.
            return self.util.sort_list(result)
        # Catches every failure crossing this layer boundary.
        except Exception as tmp2:
            # Logs the failure at this layer before rethrowing it.
            LOGGER.error("get_seat_availability failed: %s", tmp2)
            # Wraps the lower level failure into the generic exception of this codebase.
            raise ProcessingException("get_seat_availability failed: " + str(tmp2)) from None
