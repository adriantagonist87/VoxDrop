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

    context.interpolationQuality = .high
    // The supplied artwork already includes its tile and margins.
    let artwork = CGRect(x: 0, y: 0, width: CGFloat(size), height: CGFloat(size))
    let fit = min(artwork.width / CGFloat(logo.width), artwork.height / CGFloat(logo.height))
    let width = CGFloat(logo.width) * fit
    let height = CGFloat(logo.height) * fit
    let imageRect = CGRect(x: artwork.midX - width / 2, y: artwork.midY - height / 2,
                           width: width, height: height)
    context.draw(logo, in: imageRect)

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
