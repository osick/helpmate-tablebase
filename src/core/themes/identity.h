#pragma once
#include <vector>

#include "probe/solution.h"

namespace hm::themes {

// Who moved and who died on each ply, with units identified by the square
// they occupied in the DIAGRAM. `trajectories()` chains squares into paths
// but has no notion of a unit's origin; the cross-solution themes (zilahi:
// "the unit that mates here is captured there") need exactly that. The
// current type is carried too, for detectors that replay a line themselves.
struct PlyIdentity {
    int mover_origin = -1;              // diagram square of the unit that moved
    PieceType mover_type = PieceType::Pawn;  // its type AT THIS PLY: a promoted
                                        // pawn reads as its promoted type on
                                        // every later ply, and as a pawn on
                                        // the promoting ply itself
    int captured_origin = -1;           // diagram square of the captured unit,
                                        // or -1 for a quiet ply; an en-passant
                                        // victim is found beside `to`, exactly
                                        // as trajectory.cpp locates it
};

// One entry per ply, in order. Replays the solution from `s.start`.
std::vector<PlyIdentity> identities(const Solution& s);

}  // namespace hm::themes
