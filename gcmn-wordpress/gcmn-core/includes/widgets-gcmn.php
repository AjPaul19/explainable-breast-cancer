<?php
/**
 * GCMN widgets for Elementor (free). Loaded only when Elementor is ready, so this file may use Elementor classes.
 *  - GCMN Menu: the site menu with drop-downs and sub-drop-downs, and the full-screen menu on phones.
 *  - GCMN Block: numbers, giving accounts, contact details and the request forms, ready to drag in.
 *  - GCMN Pages and items: a grid of cards for stories, ministries, resources, news or the pages under a page.
 */
defined( 'ABSPATH' ) || exit;

class GCMN_Menu_Widget extends \Elementor\Widget_Base {
	public function get_name() {
		return 'gcmn-menu';
	}
	public function get_title() {
		return 'GCMN Menu';
	}
	public function get_icon() {
		return 'eicon-nav-menu';
	}
	public function get_categories() {
		return array( 'gcmn' );
	}
	public function get_keywords() {
		return array( 'menu', 'nav', 'navigation', 'header' );
	}

	protected function register_controls() {
		$menus = array();
		foreach ( wp_get_nav_menus() as $m ) {
			$menus[ $m->slug ] = $m->name;
		}
		$this->start_controls_section( 'content', array( 'label' => 'Menu' ) );
		$this->add_control( 'menu', array( 'label' => 'Menu', 'type' => \Elementor\Controls_Manager::SELECT, 'options' => $menus, 'default' => 'gcmn-primary',
			'description' => 'Add, rename and reorder the menu items under Appearance > Menus. Items can have sub-items and sub-sub-items.' ) );
		$this->end_controls_section();

		$this->start_controls_section( 'style', array( 'label' => 'Style', 'tab' => \Elementor\Controls_Manager::TAB_STYLE ) );
		$this->add_group_control( \Elementor\Group_Control_Typography::get_type(), array( 'name' => 'typo', 'selector' => '{{WRAPPER}} .nav-item > a' ) );
		$this->add_control( 'link_color', array( 'label' => 'Link colour', 'type' => \Elementor\Controls_Manager::COLOR, 'selectors' => array( '{{WRAPPER}} .nav-item > a' => 'color: {{VALUE}}' ) ) );
		$this->add_control( 'hover_bg', array( 'label' => 'Hover background', 'type' => \Elementor\Controls_Manager::COLOR, 'selectors' => array( '{{WRAPPER}} .nav-item > a:hover, {{WRAPPER}} .nav-item:focus-within > a' => 'background-color: {{VALUE}}' ) ) );
		$this->add_control( 'drop_bg', array( 'label' => 'Drop-down background', 'type' => \Elementor\Controls_Manager::COLOR, 'selectors' => array( '{{WRAPPER}} .sub' => 'background-color: {{VALUE}}' ) ) );
		$this->add_control( 'button_bg', array( 'label' => 'Highlighted item (Give) background', 'type' => \Elementor\Controls_Manager::COLOR, 'selectors' => array( '{{WRAPPER}} .nav-item.g-nav-give > a' => 'background-color: {{VALUE}}' ) ) );
		$this->end_controls_section();
	}

	protected function render() {
		$s = $this->get_settings_for_display();
		echo gcmn_menu_html( isset( $s['menu'] ) ? $s['menu'] : 'gcmn-primary' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped inside gcmn_menu_html
	}
}

class GCMN_Block_Widget extends \Elementor\Widget_Base {
	public function get_name() {
		return 'gcmn-block';
	}
	public function get_title() {
		return 'GCMN Block';
	}
	public function get_icon() {
		return 'eicon-code-highlight';
	}
	public function get_categories() {
		return array( 'gcmn' );
	}
	public function get_keywords() {
		return array( 'form', 'giving', 'stats', 'contact', 'prayer', 'mentor' );
	}

	protected function register_controls() {
		$this->start_controls_section( 'content', array( 'label' => 'Block' ) );
		$this->add_control( 'block', array( 'label' => 'Show', 'type' => \Elementor\Controls_Manager::SELECT, 'default' => 'stats', 'options' => array(
			'stats'   => 'The numbers (from Settings)',
			'giving'  => 'Giving accounts and instructions',
			'details' => 'Contact details (from Settings)',
			'contact' => 'Contact form (visitor chooses the topic)',
			'prayer'  => 'Prayer request form (visitor chooses a mentor)',
			'mentor'  => 'Talk to a mentor form',
			'submit'  => 'Staff content submission form',
		) ) );
		$this->end_controls_section();
	}

	protected function render() {
		$s   = $this->get_settings_for_display();
		$map = array(
			'stats'   => '[gcmn_stats]', 'giving' => '[gcmn_giving]', 'details' => '[gcmn_details]', 'contact' => '[gcmn_contact]',
			'prayer'  => '[gcmn_contact topic="prayer" mentors="1" button="Send my prayer request" label="Your prayer request"]',
			'mentor'  => '[gcmn_contact topic="mentor" mentors="1" button="Send to my mentor" label="Your message"]', 'submit' => '[gcmn_submit]',
		);
		$key = isset( $s['block'] ) && isset( $map[ $s['block'] ] ) ? $s['block'] : 'stats';
		echo do_shortcode( $map[ $key ] ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- shortcodes escape their own output
	}
}

class GCMN_Cards_Widget extends \Elementor\Widget_Base {
	public function get_name() {
		return 'gcmn-cards';
	}
	public function get_title() {
		return 'GCMN Pages and items';
	}
	public function get_icon() {
		return 'eicon-posts-grid';
	}
	public function get_categories() {
		return array( 'gcmn' );
	}
	public function get_keywords() {
		return array( 'posts', 'cards', 'grid', 'stories', 'news', 'list' );
	}

	protected function register_controls() {
		$this->start_controls_section( 'content', array( 'label' => 'What to show' ) );
		$this->add_control( 'source', array( 'label' => 'Show', 'type' => \Elementor\Controls_Manager::SELECT, 'default' => 'gcmn_story', 'options' => array(
			'gcmn_story' => 'Stories', 'gcmn_strategy' => 'Ministries', 'gcmn_resource' => 'Resources', 'post' => 'News', 'gcmn_event' => 'Events',
			'gcmn_prayer' => 'Prayer needs', 'gcmn_opportunity' => 'Partner opportunities', 'children' => 'The pages under a page',
		) ) );
		$pages = array( '' => 'This page' );
		foreach ( get_pages( array( 'number' => 400, 'sort_column' => 'post_title' ) ) as $p ) {
			$pages[ $p->ID ] = $p->post_title;
		}
		$this->add_control( 'parent', array( 'label' => 'Parent page', 'type' => \Elementor\Controls_Manager::SELECT, 'options' => $pages, 'default' => '', 'condition' => array( 'source' => 'children' ) ) );
		$this->add_control( 'count', array( 'label' => 'How many', 'type' => \Elementor\Controls_Manager::NUMBER, 'default' => 6, 'min' => 1, 'max' => 60 ) );
		$this->add_control( 'cols', array( 'label' => 'Columns', 'type' => \Elementor\Controls_Manager::SELECT, 'default' => '3', 'options' => array( '2' => '2', '3' => '3', '4' => '4' ) ) );
		$this->end_controls_section();
	}

	protected function render() {
		$s     = $this->get_settings_for_display();
		$src   = isset( $s['source'] ) ? $s['source'] : 'gcmn_story';
		$args  = array( 'posts_per_page' => max( 1, min( 60, (int) $s['count'] ) ), 'post_status' => 'publish', 'orderby' => 'date', 'order' => 'DESC' );
		if ( 'children' === $src ) {
			$args += array( 'post_type' => 'page', 'post_parent' => (int) $s['parent'] ?: get_the_ID(), 'orderby' => 'menu_order title', 'order' => 'ASC' );
		} else {
			$args['post_type'] = $src;
		}
		$q = new WP_Query( $args );
		echo '<div class="g-cards g-cc' . (int) $s['cols'] . '">';
		while ( $q->have_posts() ) {
			$q->the_post();
			$ex = has_excerpt() ? get_the_excerpt() : wp_trim_words( wp_strip_all_tags( strip_shortcodes( get_the_content() ) ), 22, '…' );
			echo '<article class="g-card"><h3 class="g-card-h"><a href="' . esc_url( get_permalink() ) . '">' . esc_html( get_the_title() ) . '</a></h3>' . ( $ex ? '<p class="g-card-p">' . esc_html( $ex ) . '</p>' : '' ) . '</article>';
		}
		wp_reset_postdata();
		echo '</div>';
	}
}
