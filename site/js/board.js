// A thin wrapper over the vendored cm-chessboard: show a placement, animate
// to the next one, and (for puzzles) accept drags through a validator. The
// board never knows the rules; it shows FENs the data already contains.
import { Chessboard, INPUT_EVENT_TYPE, BORDER_TYPE } from "../vendor/cm-chessboard/Chessboard.js";
import { PromotionDialog, PROMOTION_DIALOG_RESULT_TYPE } from "../vendor/cm-chessboard/extensions/promotion-dialog/PromotionDialog.js";

export function makeBoard(el, { input = false } = {}) {
  const board = new Chessboard(el, {
    position: "8/8/8/8/8/8/8/8",
    assetsUrl: "vendor/cm-chessboard/assets/",
    style: { borderType: BORDER_TYPE.none },
    extensions: input ? [{ class: PromotionDialog }] : [],
  });
  return {
    raw: board,
    // Set a full FEN; only the placement is used. Animated unless `jump`.
    show(fen, jump = false) {
      return board.setPosition(fen.split(" ")[0], !jump);
    },
    // Puzzle input. `onDrag(uci)` returns "correct" | "wrong" | "promote".
    // On "promote" the dialog asks for the piece and onDrag is called again
    // with the 5-char uci; the drag itself is rejected so the board is only
    // ever driven by show().
    enableInput(onDrag) {
      board.enableMoveInput((event) => {
        if (event.type !== INPUT_EVENT_TYPE.validateMoveInput) return true;
        const uci = `${event.squareFrom}${event.squareTo}`;
        const verdict = onDrag(uci);
        if (verdict !== "promote") return false;
        const color = event.piece.charAt(0);
        board.showPromotionDialog(event.squareTo, color, (result) => {
          if (result.type !== PROMOTION_DIALOG_RESULT_TYPE.pieceSelected) return;
          onDrag(`${uci}${result.piece.charAt(1)}`);
        });
        return false;
      });
    },
    disableInput() { try { board.disableMoveInput(); } catch { /* not enabled */ } },
  };
}
