<?php
defined( 'ABSPATH' ) || exit;

/**
 * Old addresses (from the previous website) lead to the new pages, so links people saved and search results keep working.
 * The list is the "redirects" part of the content file: old path => new path.
 */
add_action( 'template_redirect', function () {
	if ( ! is_404() ) {
		return;
	}
	$map = get_option( 'gcmn_redirects', array() );
	if ( ! $map || ! is_array( $map ) ) {
		return;
	}
	$req  = isset( $_SERVER['REQUEST_URI'] ) ? wp_parse_url( esc_url_raw( wp_unslash( $_SERVER['REQUEST_URI'] ) ), PHP_URL_PATH ) : '';
	$home = wp_parse_url( home_url(), PHP_URL_PATH );
	if ( $home && 0 === strpos( $req, $home ) ) {
		$req = substr( $req, strlen( $home ) );
	}
	$req = '/' . trim( (string) $req, '/' );
	foreach ( array( $req, preg_replace( '/\.html$/', '', $req ) ) as $try ) {
		if ( isset( $map[ $try ] ) ) {
			wp_safe_redirect( home_url( $map[ $try ] ), 301 );
			exit;
		}
	}
} );
