Site review — www.zabeehullahleghari.com (checked on desktop 1440 px and mobile 390 px)

Working well: domain + HTTPS, zabeehullahleghari.com → www redirect (308), all 11 pages load,
no console/network errors, no horizontal scroll on mobile, Privacy / FAQ / Terms pages,
og + twitter tags present, sitemap and robots.

Please fix:

1. Brand theme. The new build is dark green / sage / pink with Poppins. The approved brand is
   navy #0F2A4A, ivory #F7F3EA, antique gold #B08D57, text #1F2328 / #5B6B7F, serif headings
   (Cormorant Garamond). The previous vercel.app build matched it; please return to that palette.
   Everything else (logo, YouTube, Facebook, LinkedIn) uses it.
2. og:image: the current /images/og-image.jpg is not ours (the name is cut off at the right edge,
   pink band). Replace it with og-image.jpg from zabeehullah-leghari-web-assets.zip.
3. Favicon is still the default Next.js "N". Use favicon.ico, apple-touch-icon.png, icon-192.png,
   icon-512.png from the same zip (apple-touch-icon and icon-192 currently return 404).
4. Hero photo: the ivory/pink portrait sits on a dark background and does not match. Use
   zabeehullah-leghari-cutout.png (transparent) inside the arch, or the navy portrait.
5. Home page shows the ayah twice (pink band + footer). Keep it only in the footer; remove the band.
6. Introduction paragraph: the drop cap "Z" is detached from "abeehullah". Remove the drop cap.
7. One canonical domain: sitemap.xml, robots.txt, og:url/og:image use https://zabeehullahleghari.com
   but the site serves https://www.zabeehullahleghari.com. Use the www URL everywhere
   (metadataBase), add <link rel="canonical"> on every page, and redirect
   zabeehullah-leghari.vercel.app → https://www.zabeehullahleghari.com (it still serves a duplicate).
8. Page-specific og:title / og:description (all pages currently share the home values).
9. Social + academic icons: as in the links message; remove
   "Social and academic profiles will be listed here."
