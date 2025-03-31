class element_attribute_changed:
    def __init__(self, element_locator, attr: str, current_attr: str | None) -> None:
        self.locator = element_locator
        self.attr = attr
        self.current_attr = current_attr

    def __call__(self, driver):
        by, xpath = self.locator
        elem = driver.find_element(by, xpath)
        attr = elem.get_attribute(self.attr)

        return attr != self.current_attr