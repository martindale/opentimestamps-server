# Copyright (C) 2016 The OpenTimestamps developers
#
# This file is part of python-opentimestamps.
#
# It is subject to the license terms in the LICENSE file found in the top-level
# directory of this distribution.
#
# No part of python-opentimestamps including this file, may be copied,
# modified, propagated, or distributed except according to the terms contained
# in the LICENSE file.

"""Timestamp signature verification"""

import opentimestamps.core.serialize

class VerificationError(Exception):
    """Attestation verification errors"""

class TimeAttestation:
    """Time-attesting signature"""

    def _serialize_payload(self, ctx):
        raise NotImplementedError

    def serialize(self, ctx):
        ctx.write_bytes(self.TAG)

        payload_ctx = opentimestamps.core.serialize.BytesSerializationContext()
        self._serialize_payload(payload_ctx)

        ctx.write_varbytes(payload_ctx.getbytes())

    def __eq__(self, other):
        if isinstance(other, TimeAttestation):
            assert self.__class__ is not other.__class__ # should be implemented by subclass
            return False

        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, TimeAttestation):
            assert self.__class__ is not other.__class__ # should be implemented by subclass
            return self.TAG < other.TAG

        else:
            return NotImplemented

    @classmethod
    def deserialize(cls, ctx):
        tag = ctx.read_bytes(8)

        serialized_attestation = ctx.read_varbytes(8192) # FIXME: what should max length be?

        payload_ctx = opentimestamps.core.serialize.BytesDeserializationContext(serialized_attestation)

        if tag == PendingAttestation.TAG:
            return PendingAttestation.deserialize(payload_ctx)
        elif tag == BitcoinBlockHeaderAttestation.TAG:
            return BitcoinBlockHeaderAttestation.deserialize(payload_ctx)

        # FIXME: need to make sure extra junk at end causes failure...

        assert False

# Note how neither of these signatures actually has the time...

class PendingAttestation(TimeAttestation):
    """Pending attestation

    Commitment has been submitted for future attestation, and we have a URI to
    use to try to find out more information.
    """

    TAG = bytes.fromhex('83dfe30d2ef90c8e')

    MAX_URI_LENGTH = 1000
    """Maximum legal URI length, in bytes"""

    ALLOWED_URI_CHARS = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._/:"
    """Characters allowed in URI's

    Note how we've left out the characters necessary for parameters, queries,
    or fragments, as well as IPv6 [] notation, percent-encoding special
    characters, and @ login notation. Hopefully this keeps us out of trouble!
    """

    @classmethod
    def check_uri(cls, uri):
        """Check URI for validity

        Raises ValueError appropriately
        """
        if len(uri) > cls.MAX_URI_LENGTH:
            raise ValueError("URI exceeds maximum length")
        for char in uri:
            if char not in cls.ALLOWED_URI_CHARS:
                raise ValueError("URI contains invalid character %r" % bytes([char]))

    def __init__(self, uri):
        if not isinstance(uri, str):
            raise TypeError("URI must be a string")
        self.check_uri(uri.encode())
        self.uri = uri

    def __repr__(self):
        return 'PendingAttestation(%s)' % self.uri

    def __eq__(self, other):
        if other.__class__ is PendingAttestation:
            return self.uri == other.uri
        else:
            super().__eq__(other)

    def __lt__(self, other):
        if other.__class__ is PendingAttestation:
            return self.uri < other.uri

        else:
            super().__eq__(other)

    def __hash__(self):
        return hash(self.uri)

    def _serialize_payload(self, ctx):
        ctx.write_varbytes(self.uri.encode())

    @classmethod
    def deserialize(cls, ctx):
        utf8_uri = ctx.read_varbytes(cls.MAX_URI_LENGTH)

        try:
            cls.check_uri(utf8_uri)
        except ValueError as exp:
            raise opentimestamps.core.serialize.DeserializationError("Invalid URI: %r" % exp)

        return PendingAttestation(utf8_uri.decode())

class BitcoinBlockHeaderAttestation(TimeAttestation):
    """Signed by the Bitcoin blockchain

    The commitment digest will be the merkleroot of the blockheader; the block
    height is recorded so that looking up the correct block header in an
    external block header database doesn't require every header to be stored
    locally (33MB and counting). (remember that a memory-constrained local
    client can save an MMR that commits to all blocks, and use an external service
    to fill in pruned details).
    """

    TAG = bytes.fromhex('0588960d73d71901')

    def __init__(self, height):
        self.height = height

    def __eq__(self, other):
        if other.__class__ is BitcoinBlockHeaderAttestation:
            return self.height == other.height
        else:
            super().__eq__(other)

    def __lt__(self, other):
        if other.__class__ is BitcoinBlockHeaderAttestation:
            return self.height < other.height

        else:
            super().__eq__(other)

    def __hash__(self):
        return hash(self.height)

    def verify_against_blockheader(self, digest, block_header):
        """Verify attestation against a block header

        Returns the block time on success; raises VerificationError on failure.
        """

        if len(digest) != 32:
            raise VerificationError("Expected digest with length 32 bytes; got %d bytes" % len(digest))
        elif digest != block_header.hashMerkleRoot:
            raise VerificationError("Digest does not match merkleroot")

        return block_header.nTime

    def __repr__(self):
        return 'BitcoinBlockHeaderAttestation(%r)' % self.height

    def _serialize_payload(self, ctx):
        ctx.write_varuint(self.height)

    @classmethod
    def deserialize(cls, ctx):
        height = ctx.read_varuint()
        return BitcoinBlockHeaderAttestation(height)
