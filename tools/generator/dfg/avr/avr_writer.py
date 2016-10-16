# -*- coding: utf-8 -*-
# Copyright (c) 2013-2016, Niklas Hauser
# Copyright (c)      2016, Fabian Greif
# All rights reserved.

import itertools
import logging

from ..writer import XMLDeviceWriter
from . import avr_io

LOGGER = logging.getLogger('dfg.avr.writer')

class AVRDeviceWriter(XMLDeviceWriter):
    """ AVRDeviceWriter
    Translates the Device to a XPCC specific format.
    """
    def __init__(self, device):
        XMLDeviceWriter.__init__(self, device)

        self.root.removeAttribute('size_id')

        LOGGER.info(("Generating Device File for '%s'." % self.device.ids.string))

        self.types = self.device.ids.getAttribute('type')
        self.pin_ids = self.device.ids.getAttribute('pin_id')
        self.names = self.device.ids.getAttribute('name')
        self.family = self.device.ids.intersection.family

        # search the io dictionary for this device
        # we only need one pin name to identify the device group
        pin_name = self.device.getProperty('pin-name').values[0].value
        self.io = [a for a in avr_io.pins if pin_name in a['devices']]
        if len(self.io) > 0:
            self.io = self.io[0]
        else:
            self.io = {}
            if self.device.id.family != 'xmega':
                LOGGER.warning("IO not found for device '%s' with pin-name: '%s'", self.device.id.string, pin_name)

        self.addDeviceAttributesToNode(self.root, 'flash')
        self.addDeviceAttributesToNode(self.root, 'ram')
        self.addDeviceAttributesToNode(self.root, 'eeprom')
        self.addDeviceAttributesToNode(self.root, 'core')
        self.addDeviceAttributesToNode(self.root, 'mcu')

        pin_count_child = self.root.addChild('pin-count')
        if self.family == 'xmega':
            # the int in the type is the package device_id
            # ie. A1, B1 = 100 pins, A3, C3 = 64 pins, etc...
            pins = [0, 100, 0, 64, 44, 32]
            pin_count_child.setValue(pins[int(self.types[0][1:])])
        else:
            # the AT90, ATtiny and ATmega have very weird pin counts, with so many different packages
            pin_count_child.setValue(0)

        for header in ['avr/io.h', 'avr/interrupt.h']:
            header_child = self.root.addChild('header')
            header_child.setValue(header)

        # self.addDeviceAttributesToNode(self.root, 'define')

        core_child = self.root.addChild('driver')
        core_child.setAttributes({'type': 'core', 'name': 'avr'})

        # ADC
        self.addAdcToNode(self.root)
        # Clock
        clock_child = self.root.addChild('driver')
        clock_child.setAttributes({'type': 'clock', 'name': 'avr'})
        # DAC
        self.addDacToNode(self.root)
        # I2C aka TWI
        self.addI2cToNode(self.root)
        # SPI
        self.addSpiToNode(self.root)
        # Timer
        self.addTimerToNode(self.root)
        # UART
        self.addUartToNode(self.root)
        # USI can be used to emulate UART, SPI and I2C, so there should not be a seperate driver for it.
        # self.addUsiToNode(self.root)
        # GPIO
        self.addGpioToNode(self.root)

    def addDeviceAttributesToNode(self, node, name):
        properties = self.device.getProperty(name)

        if properties == None:
            return

        for prop in properties.values:
            for device_id in prop.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                child = node.addChild(name)
                child.setAttributes(attr)
                child.setValue(prop.value)

    def addModuleAttributesToNode(self, node, peripheral, name, family=None):
        if family == None:
            family = self.family
        modules = self.device.getProperty('modules')

        for prop in modules.values:
            if any(m for m in prop.value if m.startswith(peripheral)):
                for device_id in prop.ids.differenceFromIds(self.device.ids):
                    attr = self._getAttributeDictionaryFromId(device_id)
                    driver = node.addChild('driver')
                    driver.setAttributes(attr)
                    driver.setAttributes({'type': name, 'name': family})

    def addModuleInstancesAttributesToNode(self, node, peripheral, name, family=None):
        if family == None:
            family = self.family
        modules = self.device.getProperty('modules')

        driver = node.addChild('driver')
        driver.setAttributes({'type': name, 'name': family})

        for prop in modules.values:
            instances = []
            for module in [m for m in prop.value if m.startswith(peripheral)]:
                instances.append(module[len(peripheral):])

            if len(instances) == 0:
                continue
            instances.sort()

            for device_id in prop.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                self.addInstancesToDriver(driver, instances, attr)

                if name in self.io:
                    for io in self.io[name]:
                        ch = driver.addChild('gpio')
                        ch.setAttributes(io)

    def addI2cToNode(self, node):
        family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
        if self.family == 'xmega':
            self.addModuleInstancesAttributesToNode(node, 'TWI', 'i2c', family)
        else:
            self.addModuleAttributesToNode(node, 'TWI', 'i2c', family)

    def addSpiToNode(self, node):
        family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
        if self.family == 'xmega':
            self.addModuleInstancesAttributesToNode(node, 'SPI', 'spi', family)
        else:
            self.addModuleAttributesToNode(node, 'SPI', 'spi', family)

    def addAdcToNode(self, node):
        if self.family == 'at90' and self.types[0] in ['usb', 'can', 'pwm']:
            family = 'at90'
        else:
            family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
        if self.family == 'xmega':
            self.addModuleInstancesAttributesToNode(node, 'ADC', 'adc', family)
        else:
            self.addModuleAttributesToNode(node, 'AD_CONVERTER', 'adc', family)

    def addDacToNode(self, node):
        if self.family == 'xmega':
            self.addModuleInstancesAttributesToNode(node, 'DAC', 'dac')
        else:
            self.addModuleAttributesToNode(node, 'DA_CONVERTER', 'dac')

    def addUsiToNode(self, node):
        if self.family != 'xmega':
            family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
            self.addModuleAttributesToNode(node, 'USI', 'usi', family)

    def addTimerToNode(self, node):
        if self.family == 'xmega':
            self.addModuleInstancesAttributesToNode(node, 'TC', 'timer')
        else:
            self.addModuleInstancesAttributesToNode(node, 'TIMER_COUNTER_', 'timer')

    def addUartToNode(self, node):
        family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
        # this is special, some AT90_Tiny_Megas can put their USART into SPI mode
        # we have to parse this specially.
        uartSpi = 'uartspi' in self.io or self.family == 'xmega'
        modules = self.device.getProperty('modules')

        for prop in modules.values:
            instances = []
            for module in [m for m in prop.value if m.startswith('USART')]:
                if self.family == 'xmega':
                    instances.append(module[5:7])
                else:
                    # some device only have a 'USART', but we want 'USART0'
                    mod = module + '0'
                    instances.append(mod[5:6])

            driver = node.addChild('driver')
            driver.setAttributes({'type': 'uart', 'name': family})
            if uartSpi:
                spi_driver = node.addChild('driver')
                spi_driver.setAttributes({'type': 'spi', 'name': family + "_uart"})

            if instances != []:
                instances = list(set(instances))
                instances.sort()

                for device_id in prop.ids.differenceFromIds(self.device.ids):
                    attr = self._getAttributeDictionaryFromId(device_id)
                    self.addInstancesToDriver(driver, instances, attr)

                    if uartSpi:
                        self.addInstancesToDriver(spi_driver, instances, attr)

    def addGpioToNode(self, node):
        family = 'at90_tiny_mega' if (self.family in ['at90', 'attiny', 'atmega']) else self.family
        props = self.device.getProperty('gpios')

        driver = node.addChild('driver')
        driver.setAttributes({'type': 'gpio', 'name': family})

        for prop in props.values:
            gpios = prop.value
            gpios.sort(key=lambda k: (k['port'], k['id']))
            for device_id in prop.ids.differenceFromIds(self.device.ids):
                device_dict = self._getAttributeDictionaryFromId(device_id)
                for gpio in gpios:
                    gpio_child = driver.addChild('gpio')
                    gpio_child.setAttributes(device_dict)
                    for name in ['port', 'id', 'pcint', 'extint']:
                        if name in gpio:
                            gpio_child.setAttribute(name, gpio[name])
                    for af in gpio['af']:
                        af_child = gpio_child.addChild('af')
                        af_child.setAttributes(af)

    def _getAttributeDictionaryFromId(self, device_id):
        target = device_id.properties
        device_dict = {}
        for attr in target:
            if target[attr] != None:
                if attr == 'type':
                    device_dict['device-type'] = target[attr]
                if attr == 'name':
                    device_dict['device-name'] = target[attr]
                if attr == 'pin_id':
                    device_dict['device-pin-id'] = target[attr]
        return device_dict

    def _addNamingSchema(self):
        if self.family == 'xmega':
            naming_schema = 'at{{ family }}{{ name }}{{ type }}{{ pin_id }}'
            identifiers = list(itertools.product(("at",),
                                                 (self.family,),
                                                 self.names,
                                                 self.types,
                                                 self.pin_ids))
            devices = ['at' + d.string.replace('none', '') for d in self.device.ids]
        elif self.family == 'at90':
            naming_schema = '{{ family }}{{ type }}{{ name }}'
            identifiers = list(itertools.product((self.family,),
                                                 self.types,
                                                 self.names))
            devices = [d.string.replace('none', '') for d in self.device.ids]
        else:
            naming_schema = '{{ family }}{{ name }}{{ type }}'
            identifiers = list(itertools.product((self.family,),
                                                 self.names,
                                                 self.types))
            devices = [d.string.replace('none', '') for d in self.device.ids]

        for identifier_parts in identifiers:
            identifier = ''.join(identifier_parts).replace('none', '')

            if identifier not in devices:
                child = self.root.prependChild('invalid-device')
                child.setValue(identifier)
            else:
                devices.remove(identifier)

        for device in devices:
            LOGGER.error("Found device not matching naming schema: '{}'".format(device))

        child = self.root.prependChild('naming-schema')
        child.setValue(naming_schema)

    def write(self, folder):
        self._addNamingSchema()

        names = self.names
        names.sort(key=int)
        types = self.types
        name = self.family + "-".join(["_".join(names), "_".join(types)]) + ".xml"
        if self.family == 'xmega':
            name = name[:-4] + "-" + "_".join(self.pin_ids) + ".xml"
        self.writeToFolder(folder, name)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "AVRDeviceWriter(\n" + self.toString() + ")"
