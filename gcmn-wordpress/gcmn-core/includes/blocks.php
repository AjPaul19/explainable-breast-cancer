<?php
defined( 'ABSPATH' ) || exit;

/**
 * Blocks that read live from Settings, usable as shortcodes in any page or in Elementor's Shortcode widget.
 * They output nothing when the setting behind them is empty.
 */

/** [gcmn_stats] the sourced numbers. */
add_shortcode( 'gcmn_stats', function () {
	$stats = gcmn_stats();
	if ( ! $stats ) {
		return '';
	}
	$out = '<div class="g-stats">';
	foreach ( $stats as $s ) {
		$out .= '<div class="g-stat"><p class="g-stat-n">' . esc_html( $s['number'] ) . '</p><p class="g-stat-l">' . esc_html( $s['label'] ) . '</p></div>';
	}
	return $out . '</div>';
} );

/** [gcmn_giving] the approved giving instructions and accounts. */
add_shortcode( 'gcmn_giving', function () {
	$accounts = gcmn_giving_accounts();
	$note     = gcmn_opt( 'giving_note' );
	$mail     = gcmn_opt( 'giving_email' );
	$out      = '';
	if ( $note ) {
		$out .= '<div class="g-prose">' . gcmn_rich( $note ) . '</div>';
	}
	if ( $accounts ) {
		$out .= '<div class="g-accounts">';
		foreach ( $accounts as $a ) {
			$label = $a['bank'] . ( $a['currency'] ? ' · ' . $a['currency'] : '' );
			$out  .= '<div class="g-account"><p class="g-account-bank">' . esc_html( $a['name'] ?: $label ) . '</p>'
				. ( $a['name'] && $a['bank'] ? '<p class="g-account-chip">' . esc_html( $label ) . '</p>' : '' )
				. '<p class="g-account-no">' . esc_html( $a['number'] ) . '</p>'
				. ( $a['note'] ? '<p class="g-account-note">' . esc_html( $a['note'] ) . '</p>' : '' ) . '</div>';
		}
		$out .= '</div>';
	}
	if ( is_email( $mail ) ) {
		$out .= '<p class="g-after">Questions about giving or a receipt? Write to <a href="mailto:' . esc_attr( $mail ) . '">' . esc_html( $mail ) . '</a>.</p>';
	}
	return $out;
} );

/** [gcmn_details] contact details from Settings. */
add_shortcode( 'gcmn_details', function () {
	$rows = array();
	if ( gcmn_opt( 'email' ) ) {
		$rows['Email'] = '<a href="mailto:' . esc_attr( gcmn_opt( 'email' ) ) . '">' . esc_html( gcmn_opt( 'email' ) ) . '</a>';
	}
	if ( gcmn_opt( 'phone' ) ) {
		$rows['Phone'] = '<a href="tel:' . esc_attr( preg_replace( '/[^\d+]/', '', gcmn_opt( 'phone' ) ) ) . '">' . esc_html( gcmn_opt( 'phone' ) ) . '</a>';
	}
	if ( gcmn_opt( 'address' ) ) {
		$rows['Address'] = nl2br( esc_html( gcmn_opt( 'address' ) ) );
	}
	if ( gcmn_opt( 'hours' ) ) {
		$rows['Hours'] = esc_html( gcmn_opt( 'hours' ) );
	}
	$out = '';
	foreach ( $rows as $k => $v ) {
		$out .= '<div class="g-detail"><h3>' . esc_html( $k ) . '</h3><p>' . $v . '</p></div>';
	}
	return $out ? '<div class="g-details">' . $out . '</div>' : '';
} );

/**
 * The site menu as nested lists: drop-downs on large screens, plus the button and full-screen list for phones.
 * Used by the Elementor "GCMN Menu" widget. The theme's CSS and script style and run it.
 */
function gcmn_menu_html( $menu_slug ) {
	$items = wp_get_nav_menu_items( $menu_slug ) ?: array();
	$by    = array();
	foreach ( $items as $i ) {
		$by[ (int) $i->menu_item_parent ][] = $i;
	}
	$list = function ( $parent, $level, $sheet ) use ( &$list, $by ) {
		if ( empty( $by[ $parent ] ) ) {
			return '';
		}
		$class = 0 === $parent ? ( $sheet ? 'sheet-nav' : 'nav-list' ) : ( $sheet ? 'sheet-sub' : 'sub' );
		$out   = '<ul class="' . esc_attr( $class ) . '">';
		foreach ( $by[ $parent ] as $i ) {
			$kids = $list( (int) $i->ID, $level + 1, $sheet );
			$cls  = $sheet ? '' : 'nav-item' . ( $kids ? ' has-sub' : '' ) . ( $i->classes ? ' ' . implode( ' ', array_map( 'sanitize_html_class', array_filter( (array) $i->classes ) ) ) : '' );
			if ( ! $sheet && $level > 1 ) {
				$cls = trim( str_replace( 'nav-item', '', $cls ) ) . ( $kids ? ' has-sub' : '' );
			}
			$cur = $i->current || $i->current_item_ancestor ? ' aria-current="page"' : '';
			$out .= '<li' . ( trim( $cls ) ? ' class="' . esc_attr( trim( $cls ) ) . '"' : '' ) . '><a href="' . esc_url( $i->url ) . '"' . $cur . '>' . esc_html( $i->title ) . '</a>' . $kids . '</li>';
		}
		return $out . '</ul>';
	};
	$logo = esc_url( function_exists( 'gcmn_logo_path' ) ? gcmn_logo_path( 'light' ) : '' );
	return '<nav class="nav nav-w" aria-label="Main">' . $list( 0, 1, false ) . '</nav>'
		. '<button class="menu-btn" type="button" aria-expanded="false" aria-controls="menu-sheet"><span class="menu-label">Menu</span><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 8h16M4 16h10"/></svg></button>'
		. '<div class="sheet" id="menu-sheet" role="dialog" aria-modal="true" aria-label="Menu" hidden><div class="wrap sheet-in"><div class="sheet-top">'
		. ( $logo ? '<img src="' . $logo . '" alt="' . esc_attr( get_bloginfo( 'name' ) ) . '" width="150" height="64">' : '' )
		. '<button class="sheet-x" type="button" aria-label="Close menu"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>'
		. '<nav aria-label="Menu">' . $list( 0, 1, true ) . '</nav></div></div>';
}

/** [gcmn_section_nav] the other pages of the same section, with this page marked: the menu beside long reading pages. */
add_shortcode( 'gcmn_section_nav', function () {
	$post = get_post();
	if ( ! $post || 'page' !== $post->post_type ) {
		return '';
	}
	$parent = $post->post_parent ? get_post( $post->post_parent ) : null;
	$root   = $parent ?: $post;
	$sibs   = get_pages( array( 'parent' => $root->ID, 'sort_column' => 'menu_order,post_title', 'number' => 40, 'post_status' => 'publish' ) );
	if ( ! $sibs ) {
		return '';
	}
	$out = '<nav class="g-sidenav-in" aria-label="In this section"><p class="g-sidenav-h">In this section</p>';
	if ( $parent ) {
		$out .= '<a class="g-sidenav-up" href="' . esc_url( get_permalink( $parent ) ) . '">&larr; ' . esc_html( get_the_title( $parent ) ) . '</a>';
	}
	$out .= '<ul>';
	foreach ( $sibs as $s ) {
		$out .= '<li><a href="' . esc_url( get_permalink( $s ) ) . '"' . ( (int) $s->ID === (int) $post->ID ? ' aria-current="page"' : '' ) . '>' . esc_html( get_the_title( $s ) ) . '</a></li>';
	}
	return $out . '</ul></nav>';
} );
