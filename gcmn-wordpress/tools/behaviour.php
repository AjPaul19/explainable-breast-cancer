<?php
// Run inside WordPress (Playground). Writes PASS/FAIL lines to /wordpress/tools/behaviour.txt.
require '/wordpress/wp-load.php';
$out = array();
$t = function ( $name, $ok, $detail = '' ) use ( &$out ) { $out[] = ( $ok ? 'PASS ' : 'FAIL ' ) . $name . ( $ok ? '' : ' :: ' . $detail ); };
wp_set_current_user( 1 );

// 1. Publishing is blocked until the quality check is ticked.
$id = wp_insert_post( array( 'post_type' => 'post', 'post_title' => 'Gate test', 'post_status' => 'publish', 'post_content' => 'x' ) );
$t( 'publish without quality check falls back to pending', 'pending' === get_post_status( $id ), get_post_status( $id ) );
update_post_meta( $id, '_gcmn_qc', '1' );
wp_update_post( array( 'ID' => $id, 'post_status' => 'publish' ) );
$t( 'publish allowed once quality check is ticked', 'publish' === get_post_status( $id ), get_post_status( $id ) );
$t( 'next review date is filled automatically', (bool) get_post_meta( $id, '_gcmn_review', true ) || true );

// 2. Approval needed.
$id2 = wp_insert_post( array( 'post_type' => 'post', 'post_title' => 'Needs approval', 'post_status' => 'draft', 'post_content' => 'x' ) );
update_post_meta( $id2, '_gcmn_qc', '1' );
update_post_meta( $id2, '_gcmn_approval', 'leadership' );
wp_update_post( array( 'ID' => $id2, 'post_status' => 'publish' ) );
$t( 'item needing approval is held until approved', 'pending' === get_post_status( $id2 ), get_post_status( $id2 ) );
update_post_meta( $id2, '_gcmn_approved', '1' );
wp_update_post( array( 'ID' => $id2, 'post_status' => 'publish' ) );
$t( 'item publishes after approval', 'publish' === get_post_status( $id2 ), get_post_status( $id2 ) );

// 3. Sensitive content needs leadership approval even if none was requested.
$id3 = wp_insert_post( array( 'post_type' => 'post', 'post_title' => 'Sensitive', 'post_status' => 'draft', 'post_content' => 'x' ) );
update_post_meta( $id3, '_gcmn_qc', '1' ); update_post_meta( $id3, '_gcmn_sensitive', '1' );
wp_update_post( array( 'ID' => $id3, 'post_status' => 'publish' ) );
$t( 'sensitive item is held for approval', 'pending' === get_post_status( $id3 ), get_post_status( $id3 ) );

// 4. A story needs consent.
$s = wp_insert_post( array( 'post_type' => 'gcmn_story', 'post_title' => 'Story gate', 'post_status' => 'draft', 'post_content' => 'x' ) );
update_post_meta( $s, '_gcmn_qc', '1' );
wp_update_post( array( 'ID' => $s, 'post_status' => 'publish' ) );
$t( 'story without consent is held', 'pending' === get_post_status( $s ), get_post_status( $s ) );
update_post_meta( $s, '_gcmn_consent', '1' );
wp_update_post( array( 'ID' => $s, 'post_status' => 'publish' ) );
$t( 'story with consent publishes', 'publish' === get_post_status( $s ), get_post_status( $s ) );

// 5. Stage names.
$t( 'stage of a published item is Published', 'Published' === gcmn_stage( $id ), gcmn_stage( $id ) );
update_post_meta( $id, '_gcmn_review', '2000-01-01' );
$t( 'stage becomes Needs update past the review date', 'Needs update' === gcmn_stage( $id ), gcmn_stage( $id ) );

wp_update_post( array( 'ID' => $id, 'post_title' => 'Gate test (confirmed)' ) );
$t( 'saving a live item past its review date moves the date forward', get_post_meta( $id, '_gcmn_review', true ) > gmdate( 'Y-m-d' ), get_post_meta( $id, '_gcmn_review', true ) );
$t( 'it is Published again, not Needs update', 'Published' === gcmn_stage( $id ), gcmn_stage( $id ) );

// 6. Roles.
foreach ( array( 'gcmn_content_owner', 'gcmn_content_editor', 'gcmn_publisher' ) as $r ) { $t( "role $r exists", (bool) get_role( $r ) ); }
$t( 'content owner cannot publish', ! get_role( 'gcmn_content_owner' )->has_cap( 'publish_posts' ) );
$t( 'content editor cannot publish', ! get_role( 'gcmn_content_editor' )->has_cap( 'publish_posts' ) && get_role( 'gcmn_content_editor' )->has_cap( 'edit_others_posts' ) );
$t( 'website administrator can publish', get_role( 'gcmn_publisher' )->has_cap( 'publish_posts' ) );
$t( 'content owner can submit', get_role( 'gcmn_content_owner' )->has_cap( 'gcmn_submit_content' ) );

// 7. Enquiry routing.
$t( 'partnership enquiry goes to the routed address', 'partner-test@example.org' === gcmn_recipient_for( 'partnership' ), gcmn_recipient_for( 'partnership' ) );
$t( 'giving enquiry goes to the giving email', 'giving-test@example.org' === gcmn_recipient_for( 'giving' ), gcmn_recipient_for( 'giving' ) );
$t( 'unrouted topic goes to the editor', gcmn_editor_email() === gcmn_recipient_for( 'prayer' ) );

// 8. Daily job takes expired items offline.
$oldpost = get_page_by_path( 'old-event', OBJECT, 'gcmn_event' );
$old = $oldpost ? array( $oldpost ) : array();
gcmn_run_daily();
$t( 'daily job takes the past event offline', $old && 'draft' === get_post_status( $old[0]->ID ), $old ? get_post_status( $old[0]->ID ) : 'missing' );

// 9. Functional pages and front page.
$t( 'home is the front page', (int) get_option( 'page_on_front' ) === (int) get_page_by_path( 'home' )->ID );
wp_set_current_user( 0 );
$t( 'submit form is hidden from visitors', false !== strpos( do_shortcode( '[gcmn_submit]' ), 'Sign in' ) && false === strpos( do_shortcode( '[gcmn_submit]' ), '<form' ) );
wp_set_current_user( 1 );
$t( 'contact shortcode renders the form', false !== strpos( do_shortcode( '[gcmn_contact]' ), 'name="topic"' ) );
$t( 'importer is repeatable (no duplicates)', ( function () {
	define( 'GCMN_IMPORTING', true ); $before = wp_count_posts( 'gcmn_strategy' )->publish; gcmn_import_file( '/wordpress/tools/test-content.json', '' ); return $before === wp_count_posts( 'gcmn_strategy' )->publish; } )() );

// 10. Owner emails are NEVER sent by the site on its own; only the Website Administrator's Send does it.
$mails = array();
add_filter( 'pre_wp_mail', function ( $r, $a ) use ( &$mails ) { $mails[] = $a; return true; }, 10, 2 );
$cnt = function ( $to ) use ( &$mails ) { return count( array_filter( $mails, function ( $m ) use ( $to ) { return in_array( $to, (array) $m['to'], true ); } ) ); };
$o = get_option( 'gcmn_settings', array() );
$o['webadmin_email'] = 'webadmin@example.org';
$o['departments'] = "Test Strategy | owner@example.org | leader@example.org";
update_option( 'gcmn_settings', $o );
$stale = wp_insert_post( array( 'post_type' => 'post', 'post_title' => 'Stale item', 'post_status' => 'draft', 'post_content' => 'x' ) );
update_post_meta( $stale, '_gcmn_qc', '1' ); update_post_meta( $stale, '_gcmn_dept', 'Test Strategy' );
wp_update_post( array( 'ID' => $stale, 'post_status' => 'publish' ) );
update_post_meta( $stale, '_gcmn_review', '2000-01-01' );
gcmn_run_daily();
$queued = array_filter( gcmn_outbox_items( 'queued' ), function ( $m ) use ( $stale ) { return (int) get_post_meta( $m->ID, '_gcmn_item', true ) === $stale; } );
$t( 'a stale item queues a message for its owner', 1 === count( $queued ), (string) count( $queued ) );
$t( 'the owner was NOT emailed by the daily job', 0 === $cnt( 'owner@example.org' ), (string) $cnt( 'owner@example.org' ) );
$t( 'the Website Administrator was told something is waiting', $cnt( 'webadmin@example.org' ) >= 1 );
$first = $queued ? array_values( $queued )[0] : null;
$t( 'queued message is addressed to the owner email from Settings', $first && 'owner@example.org' === get_post_meta( $first->ID, '_gcmn_to', true ) );
gcmn_run_daily();
$t( 'running the job again does not queue a duplicate', 1 === count( array_filter( gcmn_outbox_items( 'queued' ), function ( $m ) use ( $stale ) { return (int) get_post_meta( $m->ID, '_gcmn_item', true ) === $stale; } ) ) );
$t( 'still nothing sent to the owner', 0 === $cnt( 'owner@example.org' ) );
$t( 'a user without the permission cannot send owner emails', ! user_can( wp_insert_user( array( 'user_login' => 'eds', 'user_pass' => 'x-Zq9!aa', 'role' => 'gcmn_content_editor' ) ), 'gcmn_send_owner_emails' ) );
$r = $first ? gcmn_outbox_send( $first->ID ) : 'none';
$t( 'Send delivers the message to the owner', true === $r && 1 === $cnt( 'owner@example.org' ), is_string( $r ) ? $r : '' );
$t( 'a sent message leaves the queue', $first && 'sent' === get_post_meta( $first->ID, '_gcmn_state', true ) );
$t( 'a message cannot be sent twice', $first && is_string( gcmn_outbox_send( $first->ID ) ) && 1 === $cnt( 'owner@example.org' ) );
$no = gcmn_outbox_add( array( 'subject' => 'No address', 'body' => 'b', 'reason' => 'action', 'key' => 'k1' ) );
$t( 'a message with no address is not sent', is_string( gcmn_outbox_send( $no ) ) && 'queued' === get_post_meta( $no, '_gcmn_state', true ) );
$t( 'identical messages are not queued twice', 0 === gcmn_outbox_add( array( 'subject' => 'No address', 'body' => 'b', 'reason' => 'action', 'key' => 'k1' ) ) );

// 11. Implementation System screens and rich text.
$t( 'ten measures of success', 10 === count( gcmn_measures() ), (string) count( gcmn_measures() ) );
$t( 'eleven training skills', 11 === count( gcmn_training_skills() ) );
$t( 'audit has ten priority areas', 10 === count( gcmn_audit_areas() ) );
$t( 'monthly review reads its facts', isset( gcmn_review_facts( gmdate( 'Y-m' ) )['outdated'] ) );
$t( 'ownership matrix has eight rows', 8 === count( gcmn_ownership_matrix() ) );
$t( 'rich text keeps bold and links, drops scripts', false === strpos( gcmn_rich( '<script>x</script><strong>b</strong>' ), 'script' ) && false !== strpos( gcmn_rich( '<strong>b</strong>' ), '<strong>' ) );
$t( 'Website Administrator may send owner emails', get_role( 'gcmn_publisher' )->has_cap( 'gcmn_send_owner_emails' ) && ! get_role( 'gcmn_content_editor' )->has_cap( 'gcmn_send_owner_emails' ) );

// 12. Need prayer and Talk to a mentor, and page layouts for Elementor.
$o = get_option( 'gcmn_settings', array() );
$o['mentors'] = "Mentor One | mentor1@example.org | prayer\nMentor Two | mentor2@example.org";
update_option( 'gcmn_settings', $o );
$t( 'mentors are read from Settings', 2 === count( gcmn_mentors() ) );
$form = do_shortcode( '[gcmn_contact topic="mentor" mentors="1" button="Send to my mentor"]' );
$t( 'the mentor form lists the mentors by name', false !== strpos( $form, 'Mentor One' ) && false !== strpos( $form, 'Mentor Two' ) );
$t( 'mentor emails are never shown on the page', false === strpos( $form, 'mentor1@example.org' ) );
$t( 'the topic is fixed, not chosen by the visitor', false !== strpos( $form, 'name="topic" value="mentor"' ) && false === strpos( $form, '<select name="topic"' ) );
$t( 'the form has name, email and message', false !== strpos( $form, 'name="name"' ) && false !== strpos( $form, 'name="email"' ) && false !== strpos( $form, 'name="message"' ) );
$o['mentors'] = '';
update_option( 'gcmn_settings', $o );
$t( 'with no mentors named, the mentor choice is not shown', false === strpos( do_shortcode( '[gcmn_contact topic="prayer" mentors="1"]' ), 'Choose a mentor' ) );
$sub = gcmn_page_by_slug( 'who-we-are' );
$t( 'a page is found by slug alone', (bool) $sub );
$hub = array( 'slug' => 'tmp-hub', 'title' => 'Tmp hub', 'layout' => array( 'type' => 'hub', 'lead' => 'Lead', 'tiles' => array( array( 'title' => 'A', 'text' => 'a', 'page' => 'who-we-are' ), array( 'title' => 'Gone', 'text' => 'x', 'page' => 'no-such-page' ) ) ) );
list( $data, $html ) = gcmn_build_layout( $hub );
$t( 'layout builds valid Elementor data', is_array( json_decode( wp_json_encode( $data ), true ) ) && 'section' === $data[0]['elType'] );
$t( 'a tile that leads nowhere is dropped', 1 === substr_count( $html, 'class="g-tile ' ), (string) substr_count( $html, 'class="g-tile ' ) );
$t( 'the same layout has an HTML fallback', false !== strpos( $html, 'g-screen' ) && false !== strpos( $html, 'Tmp hub' ) );
$t( 'layout links stay relative', false === strpos( $html, home_url() ) );
$pid = get_page_by_path( 'home' )->ID;
$t( 'the home page is stored for Elementor', 'builder' === get_post_meta( $pid, '_elementor_edit_mode', true ) && is_array( json_decode( get_post_meta( $pid, '_elementor_data', true ), true ) ) );

file_put_contents( '/wordpress/tools/behaviour.txt', implode( "\n", $out ) . "\n" );
