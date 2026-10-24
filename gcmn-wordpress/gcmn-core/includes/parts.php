<?php
defined( 'ABSPATH' ) || exit;

/**
 * The site header and footer as Elementor pages ("parts"), so they are edited by drag and drop like everything else.
 * The theme prints the header and footer parts when Elementor is active, and its own plain header and footer otherwise.
 * Also sets the brand colours and fonts in Elementor's Site Settings, so the colour and font pickers offer the GCMN palette.
 */
add_action( 'init', function () {
	register_post_type( 'gcmn_part', array(
		'labels'              => array( 'name' => 'Header and footer', 'singular_name' => 'Header or footer', 'edit_item' => 'Edit', 'not_found' => 'Nothing here yet' ),
		'public'              => false,
		'publicly_queryable'  => true,
		'exclude_from_search' => true,
		'show_ui'             => true,
		'show_in_menu'        => false,
		'show_in_nav_menus'   => false,
		'has_archive'         => false,
		'rewrite'             => array( 'slug' => 'site-part', 'with_front' => false ),
		'supports'            => array( 'title', 'editor', 'thumbnail' ),
		'capability_type'     => 'page',
		'map_meta_cap'        => true,
	) );
} );

/** Visitors never see a part on its own; the editor's preview (signed in) still works. */
add_action( 'template_redirect', function () {
	if ( is_singular( 'gcmn_part' ) && ! current_user_can( 'edit_pages' ) ) {
		wp_safe_redirect( home_url( '/' ), 302 );
		exit;
	}
} );
add_filter( 'wp_robots', function ( $r ) {
	if ( is_singular( 'gcmn_part' ) ) {
		$r['noindex'] = true;
	}
	return $r;
} );
add_action( 'admin_menu', function () {
	if ( current_user_can( 'edit_pages' ) ) {
		add_submenu_page( 'gcmn-tracker', 'Header and footer', 'Header and footer', 'edit_pages', 'edit.php?post_type=gcmn_part' );
	}
}, 20 );
add_filter( 'default_option_elementor_cpt_support', function ( $v ) {
	return array_values( array_unique( array_merge( (array) $v, array( 'gcmn_part' ) ) ) );
}, 20 );

function gcmn_part_id( $which ) {
	$found = get_posts( array( 'post_type' => 'gcmn_part', 'post_status' => 'publish', 'numberposts' => 1, 'fields' => 'ids', 'meta_key' => '_gcmn_part', 'meta_value' => $which ) );
	return $found ? (int) $found[0] : 0;
}

function gcmn_logo_path( $variant ) {
	return wp_make_link_relative( trailingslashit( get_theme_root_uri( 'gcmn-theme' ) ) . 'gcmn-theme/assets/img/' . ( 'light' === $variant ? 'gcmn-logo-white.png' : 'gcmn-logo.png' ) );
}

function gcmn_part_data( $which ) {
	if ( 'header' === $which ) {
		$logo = gcmn_el_widget( 'hdr-logo', 'image', array( 'image' => array( 'url' => gcmn_logo_path( 'dark' ), 'id' => '' ), 'image_size' => 'full', 'link_to' => 'custom',
			'link' => array( 'url' => '/', 'is_external' => '', 'nofollow' => '', 'custom_attributes' => '' ), '_css_classes' => 'g-hdr-logo' ) );
		$menu = gcmn_el_widget( 'hdr-menu', 'gcmn-menu', array( 'menu' => 'gcmn-primary', '_css_classes' => 'g-hdr-menu' ) );
		return array( gcmn_el_section( 'hdr-sec', 'g-header', array(
			gcmn_el_column( 'hdr-c1', 20, 'g-hdr-c1', array( $logo ) ),
			gcmn_el_column( 'hdr-c2', 80, 'g-hdr-c2', array( $menu ) ),
		) ) );
	}
	$name   = get_bloginfo( 'name' );
	$links  = array();
	foreach ( gcmn_menu_links( 'gcmn-footer' ) as $i => $l ) {
		$links[] = array( '_id' => gcmn_eid( 'ftl' . $i ), 'text' => $l[0], 'selected_icon' => array( 'value' => 'fas fa-circle', 'library' => 'fa-solid' ),
			'link' => array( 'url' => $l[1], 'is_external' => '', 'nofollow' => '', 'custom_attributes' => '' ) );
	}
	$social = array();
	foreach ( array( 'facebook' => 'Facebook', 'instagram' => 'Instagram', 'x' => 'X', 'youtube' => 'YouTube', 'linkedin' => 'LinkedIn' ) as $k => $label ) {
		if ( gcmn_opt( $k ) ) {
			$social[] = array( '_id' => gcmn_eid( 'fts' . $k ), 'text' => $label, 'selected_icon' => array( 'value' => 'fas fa-circle', 'library' => 'fa-solid' ),
				'link' => array( 'url' => gcmn_opt( $k ), 'is_external' => 'on', 'nofollow' => '', 'custom_attributes' => '' ) );
		}
	}
	$c1 = array(
		gcmn_el_widget( 'ft-logo', 'image', array( 'image' => array( 'url' => gcmn_logo_path( 'light' ), 'id' => '' ), 'image_size' => 'full', '_css_classes' => 'g-ft-logo' ) ),
	);
	if ( gcmn_opt( 'tagline' ) ) {
		$c1[] = gcmn_el_text( 'ft-tag', '<p>' . esc_html( gcmn_opt( 'tagline' ) ) . '</p>', 'g-ft-tag' );
	}
	$cols = array( gcmn_el_column( 'ft-c1', 28, 'g-ft-c', $c1 ) );
	if ( $links ) {
		$cols[] = gcmn_el_column( 'ft-c2', 24, 'g-ft-c', array( gcmn_el_heading( 'ft-h2', 'Explore', 'h2', 'g-ft-h' ), gcmn_el_widget( 'ft-l2', 'icon-list', array( 'icon_list' => $links, 'view' => 'traditional', '_css_classes' => 'g-ft-list' ) ) ) );
	}
	$cols[] = gcmn_el_column( 'ft-c3', 24, 'g-ft-c', array( gcmn_el_heading( 'ft-h3', 'Reach us', 'h2', 'g-ft-h' ), gcmn_el_widget( 'ft-d', 'shortcode', array( 'shortcode' => '[gcmn_details]', '_css_classes' => 'g-ft-details' ) ) ) );
	if ( $social ) {
		$cols[] = gcmn_el_column( 'ft-c4', 24, 'g-ft-c', array( gcmn_el_heading( 'ft-h4', 'Follow', 'h2', 'g-ft-h' ), gcmn_el_widget( 'ft-l4', 'icon-list', array( 'icon_list' => $social, 'view' => 'traditional', '_css_classes' => 'g-ft-list' ) ) ) );
	}
	return array(
		gcmn_el_section( 'ft-sec', 'g-footer', $cols ),
		gcmn_el_section( 'ft-fine', 'g-footer-fine', array( gcmn_el_column( 'ft-fc', 100, 'g-ft-fine', array( gcmn_el_text( 'ft-copy', '<p>&copy; ' . gmdate( 'Y' ) . ' ' . esc_html( $name ) . '</p>', 'g-ft-copy' ) ) ) ) ),
	);
}

/** Title and address of each item of a menu, top level only. Used for the footer part. */
function gcmn_menu_links( $menu_slug ) {
	$out   = array();
	$items = wp_get_nav_menu_items( $menu_slug ) ?: array();
	foreach ( $items as $i ) {
		if ( ! (int) $i->menu_item_parent ) {
			$out[] = array( $i->title, wp_make_link_relative( $i->url ) ?: $i->url );
		}
	}
	return $out;
}

/** Create the header and footer parts (once). Returns true if something was created. */
function gcmn_ensure_parts( $force = false ) {
	$made = false;
	foreach ( array( 'header' => 'Site header', 'footer' => 'Site footer' ) as $which => $title ) {
		$id = gcmn_part_id( $which );
		if ( $id && ! $force ) {
			continue;
		}
		$args = array( 'post_type' => 'gcmn_part', 'post_status' => 'publish', 'post_title' => $title, 'post_content' => '' );
		if ( $id ) {
			$args['ID'] = $id;
		}
		$id = wp_insert_post( $args );
		if ( $id && ! is_wp_error( $id ) ) {
			update_post_meta( $id, '_gcmn_part', $which );
			update_post_meta( $id, '_elementor_edit_mode', 'builder' );
			update_post_meta( $id, '_elementor_template_type', 'wp-page' );
			update_post_meta( $id, '_elementor_version', '3.25.0' );
			update_post_meta( $id, '_elementor_data', wp_slash( wp_json_encode( gcmn_part_data( $which ) ) ) );
			update_post_meta( $id, '_wp_page_template', 'elementor_canvas' );
			$made = true;
		}
	}
	return $made;
}

/** The theme calls this: the HTML of a part, or '' when Elementor is not available. */
function gcmn_render_part( $which ) {
	if ( ! class_exists( '\Elementor\Plugin' ) ) {
		return '';
	}
	$id = gcmn_part_id( $which );
	if ( ! $id ) {
		return '';
	}
	return (string) \Elementor\Plugin::$instance->frontend->get_builder_content_for_display( $id, true );
}

/** Brand colours and fonts in Elementor's Site Settings. Runs once per plugin version. */
add_action( 'elementor/init', function () {
	if ( get_option( 'gcmn_kit_version' ) === GCMN_VERSION || ! class_exists( '\Elementor\Plugin' ) ) {
		return;
	}
	$kit = \Elementor\Plugin::$instance->kits_manager->get_active_id();
	if ( ! $kit ) {
		return;
	}
	$s = get_post_meta( $kit, '_elementor_page_settings', true );
	$s = is_array( $s ) ? $s : array();
	$s['system_colors'] = array(
		array( '_id' => 'primary', 'title' => 'Commission Navy', 'color' => '#223C70' ),
		array( '_id' => 'secondary', 'title' => 'Hope Yellow', 'color' => '#FAD00A' ),
		array( '_id' => 'text', 'title' => 'Ink', 'color' => '#231F20' ),
		array( '_id' => 'accent', 'title' => 'Community Blue', 'color' => '#3A77C5' ),
	);
	$s['custom_colors'] = array(
		array( '_id' => 'gcmngreen', 'title' => 'Growth Green', 'color' => '#30A160' ),
		array( '_id' => 'gcmnorange', 'title' => 'Action Orange', 'color' => '#F68912' ),
		array( '_id' => 'gcmnsoft', 'title' => 'Soft background', 'color' => '#F3F6FC' ),
		array( '_id' => 'gcmnmuted', 'title' => 'Muted text', 'color' => '#505766' ),
	);
	$font = function ( $id, $title, $family, $weight ) {
		return array( '_id' => $id, 'title' => $title, 'typography_typography' => 'custom', 'typography_font_family' => $family, 'typography_font_weight' => $weight );
	};
	$s['system_typography'] = array(
		$font( 'primary', 'Headings', 'Montserrat', '800' ), $font( 'secondary', 'Subheadings', 'Montserrat', '700' ),
		$font( 'text', 'Body', 'Source Sans 3', '400' ), $font( 'accent', 'Accent', 'Source Sans 3', '700' ),
	);
	$s['default_generic_fonts'] = 'sans-serif';
	update_post_meta( $kit, '_elementor_page_settings', $s );
	if ( isset( \Elementor\Plugin::$instance->files_manager ) ) {
		\Elementor\Plugin::$instance->files_manager->clear_cache();
	}
	update_option( 'gcmn_kit_version', GCMN_VERSION, false );
}, 30 );
