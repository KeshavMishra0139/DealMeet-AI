// three.js scenes, each in its own chunk. Import these, never the scene files directly.
import { lazy } from "react";

export const HeroOrbit = lazy(() => import("./HeroOrbit"));
export const MatchMap3D = lazy(() => import("./MatchMap3D"));
export const DealFlow3D = lazy(() => import("./DealFlow3D"));
