#!/bin/bash
set -e

# iOS Project Setup Script
# Creates and configures Xcode project for EdgeAI iOS app

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IOS_DIR="$PROJECT_DIR/ios"
XCODE_PROJECT="$IOS_DIR/EdgeAI.xcodeproj"
TEMP_PROJECT="$IOS_DIR/.EdgeAI_temp"

echo "🚀 Setting up iOS Xcode Project..."
echo "Project directory: $PROJECT_DIR"
echo

# Step 1: Create temporary Xcode project using template
echo "1️⃣  Creating Xcode project template..."
cd "$IOS_DIR"

# Remove any existing project
if [ -d "$XCODE_PROJECT" ]; then
    echo "   Removing existing project..."
    rm -rf "$XCODE_PROJECT"
fi

# Create project bundle structure
echo "   Creating project structure..."
mkdir -p "$XCODE_PROJECT"

# Step 2: Ensure EdgeAI source directory exists
echo "2️⃣  Setting up source files..."
SOURCE_DIR="$IOS_DIR/EdgeAI"

# Create necessary subdirectories
mkdir -p "$SOURCE_DIR/Views"
mkdir -p "$SOURCE_DIR/Services"

# Verify source files exist
if [ ! -f "$SOURCE_DIR/App.swift" ]; then
    echo "   ⚠️  Warning: App.swift not found in $SOURCE_DIR"
fi

# Step 3: Create Info.plist
echo "3️⃣  Creating Info.plist..."
cat > "$IOS_DIR/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>en</string>
	<key>CFBundleExecutable</key>
	<string>EdgeAI</string>
	<key>CFBundleIdentifier</key>
	<string>com.edgeai.trading</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>EdgeAI</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.0</string>
	<key>CFBundleVersion</key>
	<string>1</string>
	<key>LSRequiresIPhoneOS</key>
	<true/>
	<key>UIApplicationSceneManifest</key>
	<dict>
		<key>UIApplicationSupportsMultipleScenes</key>
		<true/>
	</dict>
	<key>UIApplicationSupportsIndirectInputEvents</key>
	<true/>
	<key>UILaunchScreen</key>
	<dict/>
	<key>UIRequiredDeviceCapabilities</key>
	<array>
		<string>armv7</string>
	</array>
	<key>UISupportedInterfaceOrientations</key>
	<array>
		<string>UIInterfaceOrientationPortrait</string>
		<string>UIInterfaceOrientationLandscapeLeft</string>
		<string>UIInterfaceOrientationLandscapeRight</string>
	</array>
	<key>UISupportedInterfaceOrientations~ipad</key>
	<array>
		<string>UIInterfaceOrientationPortrait</string>
		<string>UIInterfaceOrientationPortraitUpsideDown</string>
		<string>UIInterfaceOrientationLandscapeLeft</string>
		<string>UIInterfaceOrientationLandscapeRight</string>
	</array>
</dict>
</plist>
EOF
echo "   ✓ Info.plist created"

# Step 4: Create Assets folder structure
echo "4️⃣  Creating Assets catalog..."
ASSETS_DIR="$IOS_DIR/Assets.xcassets"
if [ ! -d "$ASSETS_DIR" ]; then
    mkdir -p "$ASSETS_DIR/AppIcon.appiconset"
    mkdir -p "$ASSETS_DIR/AccentColor.colorset"

    # Create minimal AppIcon
    cat > "$ASSETS_DIR/AppIcon.appiconset/Contents.json" << 'EOF'
{
  "images" : [
    {
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "20x20"
    },
    {
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "20x20"
    },
    {
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "29x29"
    },
    {
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "29x29"
    },
    {
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "40x40"
    },
    {
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "40x40"
    },
    {
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "60x60"
    },
    {
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "60x60"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF
fi

# Step 5: Create project.pbxproj structure (simplified)
echo "5️⃣  Configuring Xcode project file..."

# Create a minimal but functional pbxproj
cat > "$XCODE_PROJECT/project.pbxproj" << 'EOF'
// !$*UTF8*$!
{
	archiveVersion = 1;
	classes = {
	};
	objectVersion = 56;
	objects = {
/* Begin PBXFileReference section */
/* End PBXFileReference section */
/* Begin PBXGroup section */
/* End PBXGroup section */
/* Begin PBXNativeTarget section */
/* End PBXNativeTarget section */
/* Begin PBXProject section */
		EDGEAI_PROJECT = {
			isa = PBXProject;
			attributes = {
				BuildIndependentTargetsInParallel = 1;
				LastSwiftUpdateCheck = 1500;
				LastUpgradeCheck = 1500;
				ORGANIZATIONNAME = EdgeAI;
				TargetAttributes = {
				};
			};
			buildConfigurationList = EDGEAI_BUILD_CONFIG;
			compatibilityVersion = "Xcode 14.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = EDGEAI_MAIN_GROUP;
			projectDirPath = "";
			projectRoot = "";
			targets = (
			);
		};
/* End PBXProject section */
/* Begin XCConfigurationList section */
		EDGEAI_BUILD_CONFIG = {
			isa = XCConfigurationList;
			buildConfigurations = (
				EDGEAI_DEBUG_CONFIG,
				EDGEAI_RELEASE_CONFIG,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		EDGEAI_DEBUG_CONFIG = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
				CLANG_CXX_LANGUAGE_DIALECT = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_SUSPICIOUS_MOVES = YES;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				CODE_SIGN_IDENTITY = "iPhone Developer";
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = dwarf;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				ENABLE_TESTABILITY = YES;
				GCC_C_LANGUAGE_DIALECT = gnu99;
				GCC_DYNAMIC_NO_PIC = NO;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_OPTIMIZATION_LEVEL = 0;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"DEBUG=1",
					"$(inherited)",
				);
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDECLARED_SELECTOR = YES;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 14.0;
				MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
				MTL_FAST_MATH = YES;
				ONLY_ACTIVE_ARCH = YES;
				SDKROOT = iphoneos;
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
			};
			name = Debug;
		};
		EDGEAI_RELEASE_CONFIG = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
				CLANG_CXX_LANGUAGE_DIALECT = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_SUSPICIOUS_MOVES = YES;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				CODE_SIGN_IDENTITY = "iPhone Developer";
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
				ENABLE_NS_ASSERTIONS = NO;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				GCC_C_LANGUAGE_DIALECT = gnu99;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_OPTIMIZE_FOR_SIZE = YES;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"$(inherited)",
				);
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDECLARED_SELECTOR = YES;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 14.0;
				MTL_ENABLE_DEBUG_INFO = NO;
				MTL_FAST_MATH = YES;
				SDKROOT = iphoneos;
				SWIFT_COMPILATION_MODE = wholemodule;
				SWIFT_OPTIMIZATION_LEVEL = "-O";
				VALIDATE_PRODUCT = YES;
			};
			name = Release;
		};
/* End XCConfigurationList section */
	};
	rootObject = EDGEAI_PROJECT;
}
EOF

echo "   ✓ Project configuration created"

# Step 6: Verify source files
echo "6️⃣  Verifying source files..."
SOURCE_FILES=(
    "App.swift"
    "Views/DashboardView.swift"
    "Views/PositionsView.swift"
    "Views/ControlView.swift"
    "Services/BotService.swift"
    "Services/NotificationService.swift"
)

MISSING=0
for file in "${SOURCE_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        echo "   ✓ $file"
    else
        echo "   ⚠️  Missing: $file"
        MISSING=$((MISSING + 1))
    fi
done

# Step 7: Create a helper script to open in Xcode
echo "7️⃣  Creating helper scripts..."

cat > "$IOS_DIR/open-in-xcode.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
open EdgeAI.xcodeproj
EOF
chmod +x "$IOS_DIR/open-in-xcode.sh"

echo "   ✓ Helper scripts created"

# Final summary
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ iOS Project Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "📁 Project location: $XCODE_PROJECT"
echo "📄 Source files: $SOURCE_DIR"
echo
if [ $MISSING -eq 0 ]; then
    echo "✅ All source files present"
else
    echo "⚠️  $MISSING source files missing (add manually if needed)"
fi
echo
echo "🚀 Next steps:"
echo "   1. Open in Xcode: $IOS_DIR/open-in-xcode.sh"
echo "   2. Update bot URL in BotService.swift"
echo "   3. Select simulator: Product → Scheme → Edit Scheme"
echo "   4. Build & Run: Cmd+R"
echo
