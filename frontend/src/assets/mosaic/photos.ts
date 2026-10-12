// Photos for the landing page's hero mosaic (features/public/DealMosaic.tsx).
//
// The mosaic has six photo slots, numbered 0 to 5, spread across its three columns. Slot N
// shows MOSAIC_PHOTOS[N]; a slot without a photo is left out, so the mosaic works with any
// number of photos, including none.
//
// To add one:
// 1. Use a photo you're licensed to use commercially, about creators and brands at work
//    (filming, a product shoot, a brand team reviewing a post). No real person may be
//    presented as a DealMeet user, so no names or handles.
// 2. Save it next to this file: portrait 4:5, about 800 x 1000 px, WebP or AVIF, under 120 KB.
//    The mosaic shows photos in black and white, so colour doesn't matter.
// 3. Import it below and add it to the list. `position` moves the crop (CSS object-position).
//
//    import studio from "./creator-studio.webp";
//    export const MOSAIC_PHOTOS: MosaicPhoto[] = [{ src: studio, position: "50% 30%" }];

export interface MosaicPhoto {
  /** The imported image file. */
  src: string;
  /** Which part of the photo stays in frame, as CSS object-position. Default: centre. */
  position?: string;
  /** Optional short label on the tile, for example "Brand shoots". */
  caption?: string;
}

export const MOSAIC_PHOTOS: MosaicPhoto[] = [];
