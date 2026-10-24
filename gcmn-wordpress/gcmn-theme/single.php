<?php
/**
 * One item: a news post, strategy, story, event, resource, prayer need or opportunity.
 * It prints only the fields the item has. It never prints who owns it or when it is reviewed.
 */
defined( 'ABSPATH' ) || exit;
get_header();
while ( have_posts() ) :
	the_post();
	$id       = get_the_ID();
	$type     = get_post_type();
	$strategy = function_exists( 'gcmn_strategy_of' ) ? gcmn_strategy_of( $id ) : null;
	$obj      = get_post_type_object( $type );
	$back_url = 'post' === $type ? get_permalink( get_option( 'page_for_posts' ) ) : get_post_type_archive_link( $type );
	$back     = 'post' === $type ? 'All news' : 'All ' . strtolower( $obj->labels->name );
	$meta     = array();
	if ( 'post' === $type ) {
		$meta[] = get_the_date( 'j F Y' );
		$cat = get_the_category();
		if ( $cat ) {
			$meta[] = $cat[0]->name;
		}
	}
	if ( 'gcmn_event' === $type ) {
		$meta[] = gcmn_t_event_dates( $id );
	}
	$loc = get_post_meta( $id, '_gcmn_location', true ) ?: get_post_meta( $id, '_gcmn_locations', true );
	if ( $loc ) {
		$meta[] = $loc;
	}
	if ( 'gcmn_story' === $type && get_post_meta( $id, '_gcmn_person', true ) ) {
		$meta[] = get_post_meta( $id, '_gcmn_person', true );
	}
	if ( 'gcmn_resource' === $type && get_post_meta( $id, '_gcmn_format', true ) ) {
		$meta[] = get_post_meta( $id, '_gcmn_format', true );
	}
	$meta = array_filter( $meta );
	$cta  = gcmn_t_cta( $id );
	if ( 'gcmn_resource' === $type && get_post_meta( $id, '_gcmn_url', true ) ) {
		$cta = array( 'Open the resource', get_post_meta( $id, '_gcmn_url', true ) );
	}
	$contact = get_post_meta( $id, '_gcmn_contact', true );
	$ask     = get_post_meta( $id, '_gcmn_ask', true );
	?>
	<section class="page-head">
		<div class="wrap">
			<?php if ( $meta ) : ?><p class="chips"><?php foreach ( $meta as $m ) : ?><span class="chip"><?php echo esc_html( $m ); ?></span><?php endforeach; ?></p><?php endif; ?>
			<h1><?php the_title(); ?></h1>
			<?php if ( $ask ) : ?><p class="lead"><?php echo esc_html( $ask ); ?></p><?php elseif ( has_excerpt() ) : ?><p class="lead"><?php echo esc_html( get_the_excerpt() ); ?></p><?php endif; ?>
		</div>
	</section>
	<section class="sec">
		<div class="wrap narrow">
			<?php if ( has_post_thumbnail() ) : ?><div class="lead-img"><?php the_post_thumbnail( 'large' ); ?></div><?php endif; ?>
			<div class="prose"><?php the_content(); ?></div>
			<?php if ( $contact ) : ?><p class="after"><strong>Contact:</strong> <?php echo esc_html( $contact ); ?></p><?php endif; ?>
			<?php if ( $strategy ) : ?><p class="after">Part of <a href="<?php echo esc_url( get_permalink( $strategy ) ); ?>"><?php echo esc_html( get_the_title( $strategy ) ); ?></a>.</p><?php endif; ?>
			<div class="actions actions-dark">
				<?php if ( $cta ) : ?><a class="btn btn-ink" href="<?php echo esc_url( $cta[1] ); ?>"><?php echo esc_html( $cta[0] ); ?></a>
				<?php elseif ( $back_url ) : ?><a class="btn btn-line-dark" href="<?php echo esc_url( $back_url ); ?>"><?php echo esc_html( $back ); ?></a><?php endif; ?>
			</div>
		</div>
	</section>
	<?php
	if ( 'gcmn_strategy' === $type ) :
		$related = new WP_Query( array(
			'post_type' => array( 'post', 'gcmn_story', 'gcmn_event', 'gcmn_resource', 'gcmn_opportunity', 'gcmn_prayer' ), 'posts_per_page' => 3, 'no_found_rows' => true,
			'meta_query' => array( array( 'key' => '_gcmn_strategy', 'value' => $id ) ),
		) );
		if ( $related->have_posts() ) :
			?>
			<section class="sec sec-soft"><div class="wrap">
				<header class="sec-head"><p class="eyebrow">From this strategy</p><h2>Latest</h2></header>
				<div class="grid"><?php while ( $related->have_posts() ) { $related->the_post(); gcmn_t_card( get_post() ); } ?></div>
			</div></section>
			<?php
			wp_reset_postdata();
		endif;
	endif;
endwhile;
get_footer();
