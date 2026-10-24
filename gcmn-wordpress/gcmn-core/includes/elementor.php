<?php
defined( 'ABSPATH' ) || exit;

/**
 * Page layouts that can be edited in Elementor (the free version is enough).
 *
 * A page entry in the content bundle can carry a "layout" (home, hub, doc or split). The importer turns it into
 *  - Elementor data (_elementor_data), so the whole page opens in Elementor and every heading, text and button is editable, and
 *  - the same page as plain HTML in the page content, which the theme shows when Elementor is not installed.
 * Both use the same CSS classes (g-screen, g-tiles, g-tile, ...) so the design lives in the theme, not in the page.
 */

/** Let Elementor edit the content types too (their own pages keep working without it). */
add_filter( 'default_option_elementor_cpt_support', function () {
	return array_values( array_unique( array_merge( array( 'page', 'post' ), array_values( gcmn_workflow_types() ) ) ) );
} );

/** A link spec -> a path on this site (kept relative so it survives a change of domain). */
function gcmn_layout_url( $e ) {
	$url = '';
	if ( ! empty( $e['page'] ) && ( $pg = gcmn_page_by_slug( $e['page'] ) ) ) {
		$url = get_permalink( $pg );
	} elseif ( ! empty( $e['item'] ) && ( $iid = gcmn_import_find( $e['item'] ) ) ) {
		$url = get_permalink( $iid );
	} elseif ( ! empty( $e['archive'] ) && post_type_exists( $e['archive'] ) ) {
		$url = get_post_type_archive_link( $e['archive'] );
	} elseif ( ! empty( $e['url'] ) ) {
		$url = $e['url'];
	}
	if ( $url && 0 === strpos( $url, '/' ) && 0 !== strpos( $url, '//' ) ) {
		$url = home_url( $url );
	}
	if ( $url && 0 === strpos( $url, home_url() ) ) {
		$url = wp_make_link_relative( $url );
	}
	return $url ?: '';
}

function gcmn_eid( $seed ) {
	return substr( md5( $seed ), 0, 7 );
}

function gcmn_el_widget( $seed, $type, array $settings ) {
	return array( 'id' => gcmn_eid( $seed ), 'elType' => 'widget', 'widgetType' => $type, 'settings' => $settings, 'elements' => array() );
}

function gcmn_el_heading( $seed, $text, $size, $class, $url = '' ) {
	$s = array( 'title' => $text, 'header_size' => $size, '_css_classes' => $class );
	if ( $url ) {
		$s['link'] = array( 'url' => $url, 'is_external' => '', 'nofollow' => '', 'custom_attributes' => '' );
	}
	return gcmn_el_widget( $seed, 'heading', $s );
}

function gcmn_el_text( $seed, $html, $class ) {
	return gcmn_el_widget( $seed, 'text-editor', array( 'editor' => $html, '_css_classes' => $class ) );
}

function gcmn_el_button( $seed, $text, $url, $class ) {
	return gcmn_el_widget( $seed, 'button', array( 'text' => $text, 'link' => array( 'url' => $url, 'is_external' => '', 'nofollow' => '', 'custom_attributes' => '' ), '_css_classes' => $class ) );
}

function gcmn_el_column( $seed, $size, $class, array $elements, array $extra = array() ) {
	return array( 'id' => gcmn_eid( $seed ), 'elType' => 'column', 'settings' => array_merge( array( '_column_size' => $size, '_inline_size' => null, 'css_classes' => $class ), $extra ), 'elements' => $elements, 'isInner' => false );
}

function gcmn_el_section( $seed, $class, array $columns, $inner = false, array $extra = array() ) {
	return array( 'id' => gcmn_eid( $seed ), 'elType' => 'section', 'settings' => array_merge( array( 'css_classes' => $class, 'content_width' => 'full', 'gap' => 'no' ), $extra ), 'elements' => $columns, 'isInner' => $inner );
}

/**
 * A picture behind an Elementor section or column, with a navy gradient on top so the words stay readable.
 * Editable in Elementor: Style > Background (picture) and Background Overlay (gradient).
 * $strength: 'strong' for panels with a lot of text, 'soft' for a tile where the picture should show.
 */
function gcmn_el_bg( $name, $media_dir, $post_id, $strength = 'strong' ) {
	if ( ! $name ) {
		return array();
	}
	$url = gcmn_bg_url( $name, $media_dir, $post_id );
	if ( ! $url ) {
		return array();
	}
	$a = 'strong' === $strength ? '0.93' : '0.88';
	$b = 'strong' === $strength ? '0.62' : '0.18';
	return array(
		'background_background' => 'classic', 'background_image' => array( 'url' => $url, 'id' => '' ), 'background_position' => 'center center', 'background_size' => 'cover', 'background_repeat' => 'no-repeat',
		'background_overlay_background' => 'gradient', 'background_overlay_color' => 'rgba(34,60,112,' . $a . ')', 'background_overlay_color_b' => 'rgba(34,60,112,' . $b . ')',
		'background_overlay_gradient_type' => 'linear', 'background_overlay_gradient_angle' => array( 'unit' => 'deg', 'size' => 165 ),
	);
}

/** The address (kept relative) of a picture of the content pack, loading it into the media library the first time. */
function gcmn_bg_url( $name, $media_dir, $post_id = 0 ) {
	static $cache = array();
	if ( isset( $cache[ $name ] ) ) {
		return $cache[ $name ];
	}
	$id  = $media_dir && function_exists( 'gcmn_import_media' ) ? gcmn_import_media( $name, $media_dir, 0 ) : 0;
	$url = $id ? wp_get_attachment_image_url( $id, 'full' ) : '';
	$cache[ $name ] = $url ? wp_make_link_relative( $url ) : '';
	return $cache[ $name ];
}

/** The same picture and gradient as inline CSS for the plain-HTML version of a page. */
function gcmn_css_bg( $name, $media_dir, $strength = 'strong' ) {
	$url = $name ? gcmn_bg_url( $name, $media_dir ) : '';
	if ( ! $url ) {
		return '';
	}
	$a = 'strong' === $strength ? '.93' : '.88';
	$b = 'strong' === $strength ? '.62' : '.18';
	return ' style="background-image:linear-gradient(165deg,rgba(34,60,112,' . $a . '),rgba(34,60,112,' . $b . ')),url(' . esc_url( $url ) . ')"';
}

/** The left-hand text block shared by home, hub and form pages. Returns array( elementor widgets, html ). */
function gcmn_layout_intro( $p, $slug ) {
	$spec = $p['layout'];
	$w    = array();
	$html = '';
	$eyebrow = isset( $spec['eyebrow'] ) ? $spec['eyebrow'] : '';
	$title   = 'home' === $spec['type'] ? ( isset( $spec['title'] ) ? $spec['title'] : gcmn_opt( 'tagline' ) ) : $p['title'];
	if ( $eyebrow ) {
		$w[]   = gcmn_el_text( $slug . 'eb', '<p>' . esc_html( $eyebrow ) . '</p>', 'g-eyebrow' );
		$html .= '<p class="g-eyebrow">' . esc_html( $eyebrow ) . '</p>';
	}
	$w[]   = gcmn_el_heading( $slug . 'h1', $title, 'h1', 'g-title' );
	$html .= '<h1 class="g-title">' . esc_html( $title ) . '</h1>';
	if ( empty( $spec['lead'] ) && 'doc' === $spec['type'] && ! empty( $p['excerpt'] ) && strlen( $p['excerpt'] ) <= 170 ) {
		$spec['lead'] = $p['excerpt']; // a doc page shows its summary under the title
	}
	if ( ! empty( $spec['lead'] ) ) {
		$w[]   = gcmn_el_text( $slug . 'lead', '<p>' . esc_html( $spec['lead'] ) . '</p>', 'g-lead' );
		$html .= '<div class="g-lead"><p>' . esc_html( $spec['lead'] ) . '</p></div>';
	}
	if ( ! empty( $spec['stats'] ) ) {
		$w[]   = gcmn_el_widget( $slug . 'st', 'shortcode', array( 'shortcode' => '[gcmn_stats]', '_css_classes' => 'g-stats-w' ) );
		$html .= '[gcmn_stats]';
	}
	if ( ! empty( $spec['cta'] ) && ( $u = gcmn_layout_url( $spec['cta'] ) ) ) {
		$w[]   = gcmn_el_button( $slug . 'cta', $spec['cta']['title'], $u, 'g-cta' );
		$html .= '<p class="g-cta-p"><a class="btn btn-gold g-cta" href="' . esc_url( $u ) . '">' . esc_html( $spec['cta']['title'] ) . '</a></p>';
	}
	return array( $w, $html );
}

/** How many tile columns a hub uses, and how many rows that makes. */
function gcmn_tile_grid( $n ) {
	$cols = $n <= 4 ? 2 : ( $n <= 6 || 9 === $n ? 3 : 4 );
	return array( $cols, (int) ceil( max( 1, $n ) / $cols ) );
}

/** Build array( elementor_data (array), html ) for a page entry with a layout. */
function gcmn_build_layout( $p, $media_dir = '', $post_id = 0 ) {
	$spec = $p['layout'];
	$slug = isset( $p['path'] ) ? $p['path'] : $p['slug'];
	$type = $spec['type'];
	list( $intro_w, $intro_h ) = gcmn_layout_intro( $p, $slug );
	$extra = isset( $spec['extra'] ) ? $spec['extra'] : '';
	$bg    = isset( $p['bg'] ) ? $p['bg'] : '';
	$lbg   = gcmn_el_bg( $bg, $media_dir, $post_id );
	$lcls  = 'g-left' . ( $lbg ? ' g-has-bg' : '' );
	$lsty  = gcmn_css_bg( $bg, $media_dir );

	if ( 'hub' === $type || 'home' === $type ) {
		$tile_cols = array();
		$tile_html = '';
		foreach ( (array) $spec['tiles'] as $i => $t ) {
			$u = gcmn_layout_url( $t );
			if ( ! $u ) {
				continue; // a tile that leads nowhere is not shown
			}
			$text = isset( $t['text'] ) ? $t['text'] : '';
			$kids = array( gcmn_el_heading( $slug . 'tt' . $i, $t['title'], 'h3', 'g-tile-h', $u ) );
			if ( $text ) {
				$kids[] = gcmn_el_text( $slug . 'tx' . $i, '<p>' . esc_html( $text ) . '</p>', 'g-tile-p' );
			}
			$timg  = ! empty( $t['img'] ) ? $t['img'] : '';
			$tbg   = gcmn_el_bg( $timg, $media_dir, $post_id, 'soft' );
			$tcls  = 'g-tile g-t' . ( $i % 8 ) . ( $tbg ? ' g-has-img' : '' );
			$tile_cols[] = gcmn_el_column( $slug . 'tc' . $i, 25, $tcls, $kids, $tbg );
			$tile_html  .= '<div class="' . $tcls . '"' . gcmn_css_bg( $timg, $media_dir, 'soft' ) . '><h3 class="g-tile-h"><a href="' . esc_url( $u ) . '">' . esc_html( $t['title'] ) . '</a></h3>' . ( $text ? '<p class="g-tile-p">' . esc_html( $text ) . '</p>' : '' ) . '</div>';
		}
		list( $cols, $rows ) = gcmn_tile_grid( count( $tile_cols ) );
		$cls   = 'g-tiles g-c' . $cols . ' g-r' . min( 5, $rows );
		$right = array( gcmn_el_section( $slug . 'in', $cls, $tile_cols, true ) );
		$rhtml = '<div class="' . $cls . '">' . $tile_html . '</div>';
		if ( $extra ) {
			$right[] = gcmn_el_text( $slug . 'ex', $extra, 'g-prose g-extra' );
			$rhtml  .= '<div class="g-prose g-extra">' . $extra . '</div>';
		}
		$data = array( gcmn_el_section( $slug . 'sec', 'g-screen g-' . $type, array(
			gcmn_el_column( $slug . 'left', 36, $lcls, $intro_w, $lbg ),
			gcmn_el_column( $slug . 'right', 64, 'g-right', $right ),
		) ) );
		$html = '<section class="g-screen g-' . $type . '"><div class="' . $lcls . '"' . $lsty . '>' . $intro_h . '</div><div class="g-right">' . $rhtml . '</div></section>';
		return array( $data, $html );
	}

	if ( 'list' === $type ) { // a long list of links: an Elementor Icon List, easy to reorder and edit
		$items = array();
		$lis   = '';
		foreach ( (array) $spec['tiles'] as $i => $t ) {
			$u = gcmn_layout_url( $t );
			if ( ! $u ) {
				continue;
			}
			$items[] = array( '_id' => gcmn_eid( $slug . 'li' . $i ), 'text' => $t['title'], 'selected_icon' => array( 'value' => 'fas fa-circle', 'library' => 'fa-solid' ),
				'link' => array( 'url' => $u, 'is_external' => '', 'nofollow' => '', 'custom_attributes' => '' ) );
			$lis    .= '<li><a href="' . esc_url( $u ) . '">' . esc_html( $t['title'] ) . '</a></li>';
		}
		$right = array( gcmn_el_widget( $slug . 'ul', 'icon-list', array( 'icon_list' => $items, 'view' => 'traditional', '_css_classes' => 'g-linklist' ) ) );
		$rhtml = '<ul class="g-links g-linklist">' . $lis . '</ul>';
		if ( $extra ) {
			$right[] = gcmn_el_text( $slug . 'ex', $extra, 'g-prose g-extra' );
			$rhtml  .= '<div class="g-prose g-extra">' . $extra . '</div>';
		}
		$data = array( gcmn_el_section( $slug . 'sec', 'g-screen g-listpage', array(
			gcmn_el_column( $slug . 'left', 34, $lcls, $intro_w, $lbg ),
			gcmn_el_column( $slug . 'right', 66, 'g-right', $right ),
		) ) );
		$html = '<section class="g-screen g-listpage"><div class="' . $lcls . '"' . $lsty . '>' . $intro_h . '</div><div class="g-right">' . $rhtml . '</div></section>';
		return array( $data, $html );
	}

	if ( 'split' === $type ) { // text on the left, a form on the right
		$sc   = $spec['shortcode'];
		$data = array( gcmn_el_section( $slug . 'sec', 'g-screen g-split', array(
			gcmn_el_column( $slug . 'left', 42, $lcls, $intro_w, $lbg ),
			gcmn_el_column( $slug . 'right', 58, 'g-right g-panel', array( gcmn_el_widget( $slug . 'sc', 'shortcode', array( 'shortcode' => $sc ) ) ) ),
		) ) );
		$html = '<section class="g-screen g-split"><div class="' . $lcls . '"' . $lsty . '>' . $intro_h . '</div><div class="g-right g-panel">' . $sc . '</div></section>';
		return array( $data, $html );
	}

	// doc: a picture banner with the title, then the section menu beside the page's own text
	$body   = isset( $p['content'] ) ? $p['content'] : '';
	$after  = isset( $spec['after'] ) ? $spec['after'] : '';
	$before = isset( $spec['before'] ) ? $spec['before'] : '';
	$right  = array();
	if ( $before ) {
		$right[] = gcmn_el_widget( $slug . 'bf', 'shortcode', array( 'shortcode' => $before ) );
	}
	$right[] = gcmn_el_text( $slug . 'body', $body, 'g-prose' );
	if ( $after ) {
		$right[] = gcmn_el_widget( $slug . 'af', 'shortcode', array( 'shortcode' => $after ) );
	}
	$bbg  = gcmn_el_bg( $bg, $media_dir, $post_id );
	$data = array(
		gcmn_el_section( $slug . 'ban', 'g-banner' . ( $bbg ? ' g-has-bg' : '' ), array( gcmn_el_column( $slug . 'bc', 100, 'g-banner-in', $intro_w ) ), false, $bbg ),
		gcmn_el_section( $slug . 'sec', 'g-screen g-doc', array(
			gcmn_el_column( $slug . 'left', 28, 'g-left g-sidenav', array( gcmn_el_widget( $slug . 'nav', 'shortcode', array( 'shortcode' => '[gcmn_section_nav]' ) ) ) ),
			gcmn_el_column( $slug . 'right', 72, 'g-right', $right ),
		) ),
	);
	$html = '<section class="g-banner' . ( $bbg ? ' g-has-bg' : '' ) . '"' . gcmn_css_bg( $bg, $media_dir ) . '><div class="g-banner-in">' . $intro_h . '</div></section>'
		. '<section class="g-screen g-doc"><div class="g-left g-sidenav">[gcmn_section_nav]</div><div class="g-right">' . $before . '<div class="g-prose">' . $body . '</div>' . $after . '</div></section>';
	return array( $data, $html );
}

/** Save a layout for a page: Elementor data, the HTML fallback and the template. */
function gcmn_apply_layout( $post_id, $p, $media_dir = '' ) {
	if ( empty( $p['layout']['type'] ) ) {
		return;
	}
	if ( ! empty( $p['content'] ) && false !== strpos( $p['content'], '[[img:' ) ) {
		$p['content'] = gcmn_import_tokens( $p['content'], $media_dir, $post_id );
	}
	list( $data, $html ) = gcmn_build_layout( $p, $media_dir, $post_id );
	wp_update_post( array( 'ID' => $post_id, 'post_content' => $html ) );
	update_post_meta( $post_id, '_gcmn_layout', $p['layout']['type'] );
	update_post_meta( $post_id, '_elementor_edit_mode', 'builder' );
	update_post_meta( $post_id, '_elementor_template_type', 'wp-page' );
	update_post_meta( $post_id, '_elementor_version', '3.25.0' );
	update_post_meta( $post_id, '_elementor_data', wp_slash( wp_json_encode( $data ) ) );
	update_post_meta( $post_id, '_wp_page_template', 'elementor_header_footer' );
}

/** Register the GCMN widgets with Elementor. */
add_action( 'elementor/elements/categories_registered', function ( $manager ) {
	$manager->add_category( 'gcmn', array( 'title' => 'GCMN', 'icon' => 'fa fa-plug' ) );
} );
add_action( 'elementor/widgets/register', function ( $widgets ) {
	require_once GCMN_DIR . 'includes/widgets-gcmn.php';
	$widgets->register( new GCMN_Menu_Widget() );
	$widgets->register( new GCMN_Block_Widget() );
	$widgets->register( new GCMN_Cards_Widget() );
} );
