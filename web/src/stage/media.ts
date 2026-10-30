/** Object URLs carry no extension, so we tag them with the media kind in the hash. */
export const tagUrl = (f: File) => URL.createObjectURL(f) + (f.type.startsWith('image/') ? '#img' : '#vid')
export const isImageUrl = (u: string) =>
  /#img$/.test(u) || /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(u) || u.startsWith('data:image')
