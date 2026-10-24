<?php
defined( 'ABSPATH' ) || exit;

/**
 * Settings page: Settings > GCMN site. Everything the theme shows about the organisation comes from here or from content.
 * A value that is empty is simply not shown on the site; nothing falls back to filler text.
 * Field types: text, email, url, textarea (plain, one entry per line), rich (formatted text).
 */
function gcmn_settings_fields() {
	return array(
		'Organisation' => array(
			'tagline'  => array( 'text', 'Tagline', 'One line shown on the home page. Leave empty to show only the organisation name.' ),
			'intro'    => array( 'rich', 'Home page introduction', 'Two or three sentences under the tagline.' ),
			'mission'  => array( 'rich', 'Mission', '' ),
			'vision'   => array( 'rich', 'Vision', '' ),
		),
		'Contact details' => array(
			'email'    => array( 'email', 'Public email', '' ),
			'phone'    => array( 'text', 'Phone', '' ),
			'whatsapp' => array( 'text', 'WhatsApp number', 'International format, digits only, for example 2348012345678.' ),
			'address'  => array( 'textarea', 'Address', '' ),
			'hours'    => array( 'text', 'Office hours', '' ),
		),
		'Social links' => array(
			'facebook'  => array( 'url', 'Facebook', '' ),
			'instagram' => array( 'url', 'Instagram', '' ),
			'x'         => array( 'url', 'X (Twitter)', '' ),
			'youtube'   => array( 'url', 'YouTube', '' ),
			'linkedin'  => array( 'url', 'LinkedIn', '' ),
		),
		'Giving' => array(
			'giving_accounts' => array( 'textarea', 'Giving accounts', 'One per line: Account name (optional) | Bank | Account number | Currency | Note (optional). Only approved accounts. Finance approves any change.' ),
			'giving_note'     => array( 'rich', 'Giving instructions', 'Shown above the accounts on the Giving page.' ),
			'giving_email'    => array( 'email', 'Giving questions go to', 'Email for giving enquiries and receipts.' ),
		),
		'Numbers' => array(
			'stats' => array( 'textarea', 'Numbers shown on the home page', 'One per line: Number | What it counts | As of (for example March 2026) | Source. A line without all four parts is not shown.' ),
		),
		'People and emails' => array(
			'webadmin_email'   => array( 'email', 'Website Administrator', 'Publishes content. Is told when content needs updating and decides whether a reminder goes to the content owner. Owners are never emailed without this person’s command.' ),
			'editor_email'     => array( 'email', 'Content Editor (Communications)', 'Receives each new submission.' ),
			'oversight_email'  => array( 'email', 'Website Oversight (Funding and Resource Mobilisation Team or relevant leadership)', 'Receives the monthly website review reminder.' ),
			'leadership_email' => array( 'email', 'Relevant leadership', 'Asked to approve content that needs Leadership approval, and any item marked sensitive.' ),
			'finance_email'    => array( 'email', 'Finance', 'Asked to approve giving and finance content.' ),
			'tech_email'       => array( 'email', 'Technical support (DS / JeNom / Operations)', 'Backups, access and training.' ),
			'departments'      => array( 'textarea', 'Departments and strategies', 'One per line: Name | Content Owner email | Strategy leader email (the approver). Use a strategy’s exact name to attach emails to it. Strategies on the site are listed automatically below.' ),
			'mentors'          => array( 'textarea', 'Mentors', 'One per line: Name | email | what they help with (optional). People who use Need prayer or Talk to a mentor choose a mentor by name; their message goes to that mentor’s email, which is never shown on the site.' ),
			'routing'          => array( 'textarea', 'Where enquiries go', 'One per line: topic | email. Topics: general, partnership, giving, serve, prayer, story. Others go to the Content Editor.' ),
		),
	);
}

add_action( 'admin_menu', function () {
	add_options_page( 'GCMN site', 'GCMN site', 'manage_options', 'gcmn-settings', 'gcmn_render_settings' );
} );

add_action( 'admin_init', function () {
	register_setting( 'gcmn_settings_group', 'gcmn_settings', array( 'sanitize_callback' => 'gcmn_sanitize_settings' ) );
} );

function gcmn_sanitize_settings( $in ) {
	$out = array();
	foreach ( gcmn_settings_fields() as $fields ) {
		foreach ( $fields as $key => $f ) {
			$v = isset( $in[ $key ] ) ? wp_unslash( $in[ $key ] ) : '';
			switch ( $f[0] ) {
				case 'email':
					$out[ $key ] = sanitize_email( $v );
					break;
				case 'url':
					$out[ $key ] = esc_url_raw( $v );
					break;
				case 'rich':
					$out[ $key ] = trim( wp_kses( $v, gcmn_rich_tags() ) );
					break;
				case 'textarea':
					$out[ $key ] = implode( "\n", array_map( 'sanitize_text_field', preg_split( '/\r\n|\r|\n/', (string) $v ) ) );
					break;
				default:
					$out[ $key ] = sanitize_text_field( $v );
			}
		}
	}
	return $out;
}

function gcmn_render_settings() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	echo '<div class="wrap"><h1>GCMN site</h1><form method="post" action="options.php">';
	settings_fields( 'gcmn_settings_group' );
	foreach ( gcmn_settings_fields() as $group => $fields ) {
		echo '<h2>' . esc_html( $group ) . '</h2><table class="form-table" role="presentation">';
		foreach ( $fields as $key => $f ) {
			$val  = gcmn_opt( $key );
			$name = 'gcmn_settings[' . $key . ']';
			echo '<tr><th scope="row"><label for="gs-' . esc_attr( $key ) . '">' . esc_html( $f[1] ) . '</label></th><td>';
			if ( 'rich' === $f[0] ) {
				wp_editor( $val, 'gs-' . $key, array( 'textarea_name' => $name, 'textarea_rows' => 6, 'media_buttons' => false, 'teeny' => true, 'quicktags' => false ) );
			} elseif ( 'textarea' === $f[0] ) {
				echo '<textarea class="large-text" rows="5" id="gs-' . esc_attr( $key ) . '" name="' . esc_attr( $name ) . '">' . esc_textarea( $val ) . '</textarea>';
			} else {
				echo '<input class="regular-text" type="' . esc_attr( in_array( $f[0], array( 'email', 'url' ), true ) ? $f[0] : 'text' ) . '" id="gs-' . esc_attr( $key ) . '" name="' . esc_attr( $name ) . '" value="' . esc_attr( $val ) . '">';
			}
			if ( $f[2] ) {
				echo '<p class="description">' . esc_html( $f[2] ) . '</p>';
			}
			if ( 'departments' === $key ) {
				$names = array();
				foreach ( get_posts( array( 'post_type' => 'gcmn_strategy', 'post_status' => 'publish', 'numberposts' => 100, 'orderby' => 'title', 'order' => 'ASC' ) ) as $s ) {
					$names[] = $s->post_title;
				}
				if ( $names ) {
					echo '<p class="description"><strong>Strategies on the site:</strong> ' . esc_html( implode( '; ', $names ) ) . '</p>';
				}
			}
			echo '</td></tr>';
		}
		echo '</table>';
	}
	submit_button();
	echo '</form></div>';
}

/** Parsed "Number | Label | As of | Source" lines. Incomplete lines are dropped so an unsourced number can never appear. */
function gcmn_stats() {
	$out = array();
	foreach ( gcmn_lines( gcmn_opt( 'stats' ) ) as $line ) {
		$p = gcmn_parts( $line, 4 );
		if ( $p[0] && $p[1] && $p[2] && $p[3] ) {
			$out[] = array( 'number' => $p[0], 'label' => $p[1], 'asof' => $p[2], 'source' => $p[3] );
		}
	}
	return $out;
}

/** Parsed giving accounts. */
function gcmn_giving_accounts() {
	$out = array();
	foreach ( gcmn_lines( gcmn_opt( 'giving_accounts' ) ) as $line ) {
		$p = gcmn_parts( $line, 5 );
		if ( $p[2] ) {
			$out[] = array( 'name' => $p[0], 'bank' => $p[1], 'number' => $p[2], 'currency' => $p[3], 'note' => $p[4] );
		}
	}
	return $out;
}

/** Tell the administrator once if nobody has been named to receive the workflow emails. */
add_action( 'admin_notices', function () {
	if ( ! current_user_can( 'manage_options' ) || gcmn_opt( 'webadmin_email' ) ) {
		return;
	}
	$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
	if ( $screen && 'settings_page_gcmn-settings' === $screen->id ) {
		return;
	}
	echo '<div class="notice notice-info"><p><strong>GCMN:</strong> add the Website Administrator’s email and the other people who take part in the workflow under <a href="' . esc_url( admin_url( 'options-general.php?page=gcmn-settings' ) ) . '">Settings &gt; GCMN site &gt; People and emails</a>, so the right person is told when content needs attention.</p></div>';
} );
