<?php
defined( 'ABSPATH' ) || exit;

define( 'GCMN_THEME_VERSION', '1.0.0' );

/** The parent theme's own stylesheet is not used: this theme ships one small stylesheet and self-hosted fonts. */
add_filter( 'hello_elementor_enqueue_style', '__return_false' );
add_filter( 'hello_elementor_enqueue_theme_style', '__return_false' );
add_filter( 'hello_elementor_header_footer', '__return_false' );

add_action( 'after_setup_theme', function () {
	add_editor_style( 'assets/css/editor-style.css' );
	add_theme_support( 'title-tag' );
	add_theme_support( 'post-thumbnails' );
	add_theme_support( 'html5', array( 'search-form', 'comment-form', 'gallery', 'caption', 'style', 'script' ) );
	add_theme_support( 'responsive-embeds' );
	add_theme_support( 'automatic-feed-links' );
	add_theme_support( 'custom-logo', array( 'height' => 80, 'width' => 200, 'flex-width' => true, 'flex-height' => true ) );
	add_image_size( 'gcmn-card', 720, 480, true );
	register_nav_menus( array( 'primary' => 'Main menu', 'footer' => 'Footer menu' ) );
}, 20 );

function gcmn_theme_logo_url( $variant = 'dark' ) {
	return get_stylesheet_directory_uri() . '/assets/img/' . ( 'light' === $variant ? 'gcmn-logo-white.png' : 'gcmn-logo.png' );
}

add_action( 'wp_enqueue_scripts', function () {
	$dir = get_stylesheet_directory();
	$uri = get_stylesheet_directory_uri();
	wp_enqueue_style( 'gcmn-fonts', $uri . '/assets/fonts/fonts.css', array(), GCMN_THEME_VERSION );
	wp_enqueue_style( 'gcmn-theme', $uri . '/assets/css/theme.css', array( 'gcmn-fonts' ), filemtime( $dir . '/assets/css/theme.css' ) );
	wp_enqueue_script( 'gcmn-theme', $uri . '/assets/js/theme.js', array(), filemtime( $dir . '/assets/js/theme.js' ), array( 'strategy' => 'defer', 'in_footer' => true ) );
}, 20 );

/** Load the two fonts early so text does not jump. */
add_action( 'wp_head', function () {
	$u = get_stylesheet_directory_uri() . '/assets/fonts/';
	echo '<link rel="preload" href="' . esc_url( $u . 'Montserrat.woff2' ) . '" as="font" type="font/woff2" crossorigin>' . "\n";
	echo '<link rel="preload" href="' . esc_url( $u . 'SourceSans3.woff2' ) . '" as="font" type="font/woff2" crossorigin>' . "\n";
	echo '<meta name="theme-color" content="#223C70">' . "\n";
	if ( ! has_site_icon() ) {
		echo '<link rel="icon" href="' . esc_url( get_stylesheet_directory_uri() . '/assets/img/gcmn-mark.png' ) . '" type="image/png">' . "\n";
	}
}, 1 );

add_action( 'init', function () {
	remove_action( 'wp_head', 'print_emoji_detection_script', 7 );
	remove_action( 'wp_print_styles', 'print_emoji_styles' );
} );

/** Drop the block-library CSS on pages that use no blocks. */
add_action( 'wp_enqueue_scripts', function () {
	if ( ! is_singular() || ! has_blocks() ) {
		wp_dequeue_style( 'wp-block-library' );
		wp_dequeue_style( 'global-styles' );
	}
}, 100 );

/** The theme needs its companion plugin. Say so plainly in the admin if it is missing. */
add_action( 'admin_notices', function () {
	if ( ! function_exists( 'gcmn_opt' ) && current_user_can( 'activate_plugins' ) ) {
		echo '<div class="notice notice-error"><p>The GCMN theme needs the <strong>GCMN Core</strong> plugin. Please install and activate it.</p></div>';
	}
} );

/** Read a setting safely even when the plugin is off. */
function gcmn_t_opt( $key, $default = '' ) {
	return function_exists( 'gcmn_opt' ) ? gcmn_opt( $key, $default ) : $default;
}

/** Page URL by slug if that page is published, else ''. */
function gcmn_t_page_url( array $slugs ) {
	foreach ( $slugs as $slug ) {
		$p = get_page_by_path( $slug );
		if ( $p && 'publish' === $p->post_status ) {
			return get_permalink( $p );
		}
	}
	return '';
}

/** Number of published items of a post type. Used to show a section only when it has something in it. */
function gcmn_t_count( $type ) {
	$c = wp_count_posts( $type );
	return $c ? (int) $c->publish : 0;
}

/**
 * Main menu. Uses the menu set in Appearance > Menus; if none is set, builds one from what is actually on the site,
 * so it never links to a section that has no content.
 */
function gcmn_t_menu_items( $location = 'primary' ) {
	$locs = get_nav_menu_locations();
	if ( ! empty( $locs[ $location ] ) ) {
		$items = wp_get_nav_menu_items( $locs[ $location ] );
		if ( $items ) {
			$all = array();
			foreach ( $items as $i ) {
				$all[ (int) $i->ID ] = array( 'title' => $i->title, 'url' => $i->url, 'current' => (bool) $i->current || (bool) $i->current_item_ancestor || (bool) $i->current_item_parent, 'class' => implode( ' ', array_filter( (array) $i->classes ) ), 'parent' => (int) $i->menu_item_parent, 'children' => array() );
			}
			$out = array();
			foreach ( $all as $id => $it ) {
				if ( $it['parent'] && isset( $all[ $it['parent'] ] ) ) {
					$all[ $it['parent'] ]['children'][] = &$all[ $id ];
				}
			}
			foreach ( $all as $id => $it ) {
				if ( ! $it['parent'] ) {
					$out[] = $all[ $id ];
				}
			}
			return $out;
		}
	}
	$out  = array();
	$skip = array( 'home', 'news', 'contact', 'submit-content' );
	foreach ( get_pages( array( 'parent' => 0, 'sort_column' => 'menu_order,post_title', 'post_status' => 'publish' ) ) as $p ) {
		if ( ! in_array( $p->post_name, $skip, true ) ) {
			$out[] = array( 'title' => $p->post_title, 'url' => get_permalink( $p ), 'current' => is_page( $p->ID ), 'class' => '', 'children' => array() );
		}
	}
	$archives = array( 'gcmn_strategy' => 'Strategies', 'gcmn_story' => 'Stories', 'gcmn_resource' => 'Resources', 'gcmn_prayer' => 'Prayer', 'gcmn_event' => 'Events' );
	foreach ( $archives as $type => $label ) {
		if ( gcmn_t_count( $type ) ) {
			$out[] = array( 'title' => $label, 'url' => get_post_type_archive_link( $type ), 'current' => is_post_type_archive( $type ), 'class' => '', 'children' => array() );
		}
	}
	if ( wp_count_posts( 'post' )->publish ) {
		$out[] = array( 'title' => 'News and updates', 'url' => get_permalink( get_option( 'page_for_posts' ) ) ?: home_url( '/news/' ), 'current' => is_home(), 'class' => '', 'children' => array() );
	}
	$c = gcmn_t_page_url( array( 'contact' ) );
	if ( $c ) {
		$out[] = array( 'title' => 'Contact', 'url' => $c, 'current' => is_page( 'contact' ), 'class' => '', 'children' => array() );
	}
	return $out;
}

/** Resolve a call-to-action from a post's own fields. Returns array( label, url ) or null. */
function gcmn_t_cta( $post_id ) {
	$label = get_post_meta( $post_id, '_gcmn_cta_label', true );
	$url   = get_post_meta( $post_id, '_gcmn_cta_url', true );
	if ( $label && $url ) {
		return array( $label, $url );
	}
	$key = get_post_meta( $post_id, '_gcmn_cta_key', true );
	if ( $key && 'read' !== $key && function_exists( 'gcmn_cta_choices' ) ) {
		$choices = gcmn_cta_choices();
		$u       = gcmn_cta_url( $key, $post_id );
		if ( $u && isset( $choices[ $key ] ) ) {
			return array( $choices[ $key ], $u );
		}
	}
	return null;
}

/** A short, human date range for an event. */
function gcmn_t_event_dates( $post_id ) {
	$s = get_post_meta( $post_id, '_gcmn_start', true );
	$e = get_post_meta( $post_id, '_gcmn_end', true );
	if ( ! $s ) {
		return '';
	}
	$a = strtotime( $s );
	$b = $e ? strtotime( $e ) : 0;
	if ( ! $b || $b === $a ) {
		return wp_date( 'j F Y', $a );
	}
	return ( wp_date( 'Y-m', $a ) === wp_date( 'Y-m', $b ) )
		? wp_date( 'j', $a ) . ' to ' . wp_date( 'j F Y', $b )
		: wp_date( 'j F Y', $a ) . ' to ' . wp_date( 'j F Y', $b );
}

/** One card in a grid, for any content type. */
function gcmn_t_card( $post = null ) {
	get_template_part( 'template-parts/card', null, array( 'post' => get_post( $post ) ) );
}

/** Elementor would load Google Fonts by default; the theme serves its own fonts. */
add_filter( 'elementor/frontend/print_google_fonts', '__return_false' );

/** A colour for each section of the site: the body gets sec-<section> so the CSS can tint tiles, glows and the menu beside the text. */
add_filter( 'body_class', function ( $classes ) {
	$map = array( 'gcmn_strategy' => 'ministries', 'gcmn_story' => 'how-to-know-god', 'gcmn_resource' => 'train-and-grow', 'gcmn_prayer' => 'need-prayer', 'gcmn_opportunity' => 'opportunities' );
	$sec = '';
	if ( is_page() ) {
		$p = get_queried_object();
		if ( $p ) {
			$anc = array_reverse( get_post_ancestors( $p ) );
			$sec = $anc ? get_post_field( 'post_name', $anc[0] ) : $p->post_name;
			if ( in_array( $sec, array( 'who-we-are', 'what-we-do', 'our-values', 'our-history', 'statement-of-faith', 'contact' ), true ) ) {
				$sec = 'about-us';
			} elseif ( 'serve' === $sec ) {
				$sec = 'opportunities';
			}
		}
	} elseif ( is_singular() || is_post_type_archive() ) {
		$t   = is_singular() ? get_post_type() : get_query_var( 'post_type' );
		$sec = isset( $map[ $t ] ) ? $map[ $t ] : '';
	}
	if ( $sec ) {
		$classes[] = 'sec-' . sanitize_html_class( $sec );
	}
	return $classes;
} );
