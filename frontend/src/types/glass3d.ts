export interface ScoringZone {
  score: number
  y_top: number
  y_bottom: number
  label: string
  position: 'above' | 'green' | 'below'
  height_frac_top: number   // 0.0 = rim, 1.0 = base
  height_frac_bottom: number
}

export interface HoleZones {
  hole_ref: number
  zones: ScoringZone[]
}

export interface GlassTemplate {
  glass_height: number
  top_radius: number
  bottom_radius: number
  wall_thickness: number
  base_thickness: number
  inner_r: number
  outer_r: number
  sector_angle: number
  sector_angle_deg: number
  slant_height: number
  volume_ml: number
}

export interface Glass3DData {
  wrap_svg: string
  zones_by_hole: HoleZones[]
  glass_template: GlassTemplate
  holes_per_glass: number
}
