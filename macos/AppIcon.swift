import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let logoURL = URL(fileURLWithPath: CommandLine.arguments[1])
let iconSet = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!

guard let source = CGImageSourceCreateWithURL(logoURL as CFURL, nil),
      let logo = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    throw CocoaError(.fileReadCorruptFile)
}

func writeIcon(_ size: Int, to url: URL) throws {
    guard let context = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                                  bytesPerRow: 0, space: colorSpace,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
        throw CocoaError(.fileWriteUnknown)
    }

    let scale = CGFloat(size) / 1024
    context.scaleBy(x: scale, y: scale)
    context.interpolationQuality = .high
    let bounds = CGRect(x: 96, y: 96, width: 832, height: 832)
    let tile = CGPath(roundedRect: bounds, cornerWidth: 180, cornerHeight: 180, transform: nil)

    context.saveGState()
    context.setShadow(offset: CGSize(width: 0, height: -12), blur: 26,
                      color: CGColor(red: 0.03, green: 0.16, blue: 0.09, alpha: 0.28))
    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.addPath(tile)
    context.fillPath()
    context.restoreGState()

    context.addPath(tile)
    context.clip()
    let artwork = bounds.insetBy(dx: 30, dy: 30)
    let fit = min(artwork.width / CGFloat(logo.width), artwork.height / CGFloat(logo.height))
    let width = CGFloat(logo.width) * fit
    let height = CGFloat(logo.height) * fit
    let imageRect = CGRect(x: artwork.midX - width / 2, y: artwork.midY - height / 2,
                           width: width, height: height)
    context.draw(logo, in: imageRect)

    context.setStrokeColor(CGColor(red: 0.05, green: 0.28, blue: 0.15, alpha: 0.15))
    context.setLineWidth(9)
    context.addPath(tile)
    context.strokePath()

    guard let image = context.makeImage(),
          let output = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        throw CocoaError(.fileWriteUnknown)
    }
    CGImageDestinationAddImage(output, image, nil)
    guard CGImageDestinationFinalize(output) else { throw CocoaError(.fileWriteUnknown) }
}

for size in [16, 32, 128, 256, 512] {
    try writeIcon(size, to: iconSet.appendingPathComponent("icon_\(size)x\(size).png"))
    try writeIcon(size * 2, to: iconSet.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
}
